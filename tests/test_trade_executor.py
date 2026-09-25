import pytest

from execution.trade_executor import TradeExecutor


class FakeExchange:
    pass


class FakeOrderEngine:
    def __init__(self):
        self.calls = []

    def prepare_order(self, symbol, trade_plan):
        self.calls.append((symbol, trade_plan))

        return {
            "category": "linear",
            "symbol": symbol,
            "side": "Buy",
            "orderType": "Limit",
            "qty": "0.003",
            "price": "86854.10",
        }


class FakePositionManager:
    pass


def make_executor():
    order_engine = FakeOrderEngine()

    executor = TradeExecutor(
        exchange=FakeExchange(),
        order_engine=order_engine,
        position_manager=FakePositionManager(),
    )

    return executor, order_engine


def test_prepare_trade_delegates_guardian_plan_to_order_engine():
    executor, order_engine = make_executor()

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
        "direction": "long",
        "position_size": "0.003",
        "entry_price": "86854.137",
        "stop_loss": "86001.234",
        "take_profit": "88555.678",
    }

    result = executor.prepare_trade(
        "btcusdt",
        trade_plan,
    )

    assert result["symbol"] == "BTCUSDT"

    assert order_engine.calls == [
        ("BTCUSDT", trade_plan),
    ]


def test_prepare_trade_rejects_non_guardian_plan():
    executor, order_engine = make_executor()

    with pytest.raises(
        ValueError,
        match="Only GUARDIAN_APPROVED",
    ):
        executor.prepare_trade(
            "BTCUSDT",
            {
                "status": "NO_TRADE",
            },
        )

    assert order_engine.calls == []


def test_prepare_trade_requires_symbol():
    executor, order_engine = make_executor()

    with pytest.raises(
        ValueError,
        match="Symbol is required",
    ):
        executor.prepare_trade(
            "",
            {
                "status": "GUARDIAN_APPROVED",
            },
        )

    assert order_engine.calls == []


def test_prepare_trade_requires_dictionary():
    executor, order_engine = make_executor()

    with pytest.raises(
        ValueError,
        match="Trade plan must be a dictionary",
    ):
        executor.prepare_trade(
            "BTCUSDT",
            None,
        )

    assert order_engine.calls == []


class FakePositionManager:
    def __init__(self, has_active_position=False):
        self.has_active_position = has_active_position
        self.requested_symbol = None

    def has_position(self, symbol):
        self.requested_symbol = symbol
        return self.has_active_position

    def reconcile_position(
        self,
        symbol,
        expected_side=None,
        expected_size=0.0,
    ):
        state = self.get_position_state(symbol)

        if expected_size == 0:
            status = (
                "MATCH"
                if not state["has_position"]
                else "UNEXPECTED_POSITION"
            )
        elif not state["has_position"]:
            status = "MISSING_POSITION"
        elif expected_side is not None and state["side"] != expected_side:
            status = "POSITION_MISMATCH"
        elif state["size"] != expected_size:
            status = "SIZE_MISMATCH"
        else:
            status = "MATCH"

        return {
            "symbol": symbol.upper(),
            "status": status,
            "expected_side": expected_side,
            "expected_size": expected_size,
            "actual_side": state["side"],
            "actual_size": state["size"],
            "actual_entry_price": state["entry_price"],
            "actual_unrealized_pnl": state["unrealized_pnl"],
        }


def test_ensure_no_existing_position_blocks_active_position():
    position_manager = FakePositionManager(True)

    executor = TradeExecutor(
        exchange=FakeExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=position_manager,
    )

    with pytest.raises(
        RuntimeError,
        match="Active position already exists for BTCUSDT",
    ):
        executor.ensure_no_existing_position("btcusdt")

    assert position_manager.requested_symbol == "BTCUSDT"


def test_ensure_no_existing_position_allows_when_flat():
    position_manager = FakePositionManager(False)

    executor = TradeExecutor(
        exchange=FakeExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=position_manager,
    )

    result = executor.ensure_no_existing_position("btcusdt")

    assert result is None
    assert position_manager.requested_symbol == "BTCUSDT"


class RecordingExchange:
    def __init__(self):
        self.calls = []

    def get_open_orders(self, symbol=None):
        return []

    def create_order(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "orderId": "TEST-ORDER-123",
            "orderStatus": "New",
        }


def test_submit_entry_submits_prepared_order_to_exchange():
    exchange = RecordingExchange()
    order_engine = FakeOrderEngine()

    executor = TradeExecutor(
        exchange=exchange,
        order_engine=order_engine,
        position_manager=FakePositionManager(False),
    )

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
        "direction": "long",
        "position_size": "0.003",
        "entry_price": "86854.137",
        "stop_loss": "86001.234",
        "take_profit": "88555.678",
    }

    result = executor.submit_entry(
        "btcusdt",
        trade_plan,
    )

    assert result["orderId"] == "TEST-ORDER-123"

    assert exchange.calls == [
        {
            "symbol": "BTCUSDT",
            "side": "Buy",
            "order_type": "Limit",
            "qty": "0.003",
            "price": "86854.10",
        }
    ]


def test_submit_entry_returns_exchange_order_response_without_assuming_fill():
    exchange = RecordingExchange()
    order_engine = FakeOrderEngine()

    executor = TradeExecutor(
        exchange=exchange,
        order_engine=order_engine,
        position_manager=FakePositionManager(False),
    )

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
        "direction": "long",
        "position_size": "0.003",
        "entry_price": "86854.137",
        "stop_loss": "86001.234",
        "take_profit": "88555.678",
    }

    result = executor.submit_entry(
        "btcusdt",
        trade_plan,
    )

    assert result["orderStatus"] == "New"
    assert result["orderId"] == "TEST-ORDER-123"


def test_submit_entry_blocks_when_open_entry_order_exists():
    class OpenOrderExchange(RecordingExchange):
        def get_open_orders(self, symbol=None):
            return [
                {
                    "orderId": "EXISTING-ORDER-001",
                    "symbol": "BTCUSDT",
                    "side": "Buy",
                    "orderType": "Limit",
                    "orderStatus": "New",
                }
            ]

    exchange = OpenOrderExchange()
    order_engine = FakeOrderEngine()

    executor = TradeExecutor(
        exchange=exchange,
        order_engine=order_engine,
        position_manager=FakePositionManager(False),
    )

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
        "direction": "long",
        "position_size": "0.003",
        "entry_price": "86854.137",
        "stop_loss": "86001.234",
        "take_profit": "88555.678",
    }

    with pytest.raises(
        RuntimeError,
        match="Open entry order already exists for BTCUSDT",
    ):
        executor.submit_entry(
            "btcusdt",
            trade_plan,
        )

    assert exchange.calls == []
    assert order_engine.calls == []


def test_verify_filled_position_matches_expected_entry():
    position_manager = FakePositionManager(False)

    position_manager.get_position_state = lambda symbol: {
        "symbol": "BTCUSDT",
        "has_position": True,
        "side": "Buy",
        "size": 0.003,
        "entry_price": 86854.10,
        "unrealized_pnl": 0.0,
    }

    executor = TradeExecutor(
        exchange=FakeExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=position_manager,
    )

    result = executor.verify_position(
        "btcusdt",
        {
            "side": "Buy",
            "qty": "0.003",
        },
    )

    assert result["status"] == "MATCH"
    assert result["symbol"] == "BTCUSDT"
    assert result["actual_side"] == "Buy"
    assert result["actual_size"] == 0.003


def test_verify_position_detects_missing_filled_position():
    position_manager = FakePositionManager(False)

    position_manager.get_position_state = lambda symbol: {
        "symbol": "BTCUSDT",
        "has_position": False,
        "side": None,
        "size": 0.0,
        "entry_price": 0.0,
        "unrealized_pnl": 0.0,
    }

    executor = TradeExecutor(
        exchange=FakeExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=position_manager,
    )

    result = executor.verify_position(
        "btcusdt",
        {
            "side": "Buy",
            "qty": "0.003",
        },
    )

    assert result["status"] == "MISSING_POSITION"
    assert result["symbol"] == "BTCUSDT"


def test_verify_position_detects_side_mismatch():
    position_manager = FakePositionManager(False)

    position_manager.get_position_state = lambda symbol: {
        "symbol": "BTCUSDT",
        "has_position": True,
        "side": "Sell",
        "size": 0.003,
        "entry_price": 86854.10,
        "unrealized_pnl": 0.0,
    }

    executor = TradeExecutor(
        exchange=FakeExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=position_manager,
    )

    result = executor.verify_position(
        "btcusdt",
        {
            "side": "Buy",
            "qty": "0.003",
        },
    )

    assert result["status"] == "POSITION_MISMATCH"
    assert result["expected_side"] == "Buy"
    assert result["actual_side"] == "Sell"


def test_verify_position_detects_size_mismatch():
    position_manager = FakePositionManager(False)

    position_manager.get_position_state = lambda symbol: {
        "symbol": "BTCUSDT",
        "has_position": True,
        "side": "Buy",
        "size": 0.002,
        "entry_price": 86854.10,
        "unrealized_pnl": 0.0,
    }

    executor = TradeExecutor(
        exchange=FakeExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=position_manager,
    )

    result = executor.verify_position(
        "btcusdt",
        {
            "side": "Buy",
            "qty": "0.003",
        },
    )

    assert result["status"] == "SIZE_MISMATCH"
    assert result["expected_size"] == 0.003
    assert result["actual_size"] == 0.002


def test_verify_position_rejects_invalid_expected_quantity():
    executor = TradeExecutor(
        exchange=FakeExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=FakePositionManager(False),
    )

    with pytest.raises(
        ValueError,
        match="Expected order quantity must be numeric",
    ):
        executor.verify_position(
            "btcusdt",
            {
                "side": "Buy",
                "qty": "not-a-number",
            },
        )


def test_apply_protection_requires_matching_position():
    class ProtectionExchange:
        def __init__(self):
            self.calls = []

        def set_trading_stop(self, **kwargs):
            self.calls.append(kwargs)
            return {"retCode": 0}

    class ProtectionOrderEngine(FakeOrderEngine):
        def prepare_protection_orders(self, symbol, trade_plan):
            return {
                "category": "linear",
                "symbol": symbol,
                "tpslMode": "Full",
                "positionIdx": 0,
                "stopLoss": "86001.20",
                "takeProfit": "88555.60",
                "slTriggerBy": "MarkPrice",
                "tpTriggerBy": "MarkPrice",
            }

    class NonMatchingPositionManager(FakePositionManager):
        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            return {
                "symbol": symbol.upper(),
                "status": "MISSING_POSITION",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": None,
                "actual_size": 0.0,
                "actual_entry_price": 0.0,
                "actual_unrealized_pnl": 0.0,
            }

    exchange = ProtectionExchange()

    executor = TradeExecutor(
        exchange=exchange,
        order_engine=ProtectionOrderEngine(),
        position_manager=NonMatchingPositionManager(False),
    )

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
        "direction": "long",
        "position_size": "0.003",
        "entry_price": "86854.137",
        "stop_loss": "86001.234",
        "take_profit": "88555.678",
    }

    with pytest.raises(
        RuntimeError,
        match="Position verification failed",
    ):
        executor.apply_protection(
            "btcusdt",
            trade_plan,
            {
                "side": "Buy",
                "qty": "0.003",
            },
        )

    assert exchange.calls == []


def test_apply_protection_submits_protection_after_matching_position():
    class ProtectionExchange:
        def __init__(self):
            self.calls = []

        def set_trading_stop(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "retCode": 0,
                "result": {
                    "status": "OK",
                },
            }

    class ProtectionOrderEngine(FakeOrderEngine):
        def prepare_protection_orders(self, symbol, trade_plan):
            return {
                "category": "linear",
                "symbol": symbol,
                "tpslMode": "Full",
                "positionIdx": 0,
                "stopLoss": "86001.20",
                "takeProfit": "88555.60",
                "slTriggerBy": "MarkPrice",
                "tpTriggerBy": "MarkPrice",
            }

    class MatchingPositionManager(FakePositionManager):
        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            return {
                "symbol": symbol.upper(),
                "status": "MATCH",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": "Buy",
                "actual_size": 0.003,
                "actual_entry_price": 86854.10,
                "actual_unrealized_pnl": 0.0,
            }

    exchange = ProtectionExchange()

    executor = TradeExecutor(
        exchange=exchange,
        order_engine=ProtectionOrderEngine(),
        position_manager=MatchingPositionManager(False),
    )

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
        "direction": "long",
        "position_size": "0.003",
        "entry_price": "86854.137",
        "stop_loss": "86001.234",
        "take_profit": "88555.678",
    }

    result = executor.apply_protection(
        "btcusdt",
        trade_plan,
        {
            "side": "Buy",
            "qty": "0.003",
        },
    )

    assert result["retCode"] == 0

    assert exchange.calls == [
        {
            "symbol": "BTCUSDT",
            "stop_loss": "86001.20",
            "take_profit": "88555.60",
            "position_idx": 0,
            "tpsl_mode": "Full",
            "sl_trigger_by": "MarkPrice",
            "tp_trigger_by": "MarkPrice",
        }
    ]


def test_execute_trade_blocks_when_open_entry_order_exists():
    class OpenOrderExchange(RecordingExchange):
        def get_open_orders(self, symbol=None):
            return [
                {
                    "orderId": "EXISTING-ORDER-002",
                    "symbol": "BTCUSDT",
                    "side": "Buy",
                    "orderType": "Limit",
                    "orderStatus": "New",
                }
            ]

    exchange = OpenOrderExchange()
    order_engine = FakeOrderEngine()

    class FlatPositionManager:
        def has_position(self, symbol):
            return False

        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            return {
                "symbol": symbol.upper(),
                "status": "MISSING_POSITION",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": None,
                "actual_size": 0.0,
                "actual_entry_price": 0.0,
                "actual_unrealized_pnl": 0.0,
            }

    executor = TradeExecutor(
        exchange=exchange,
        order_engine=order_engine,
        position_manager=FlatPositionManager(),
    )

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
        "direction": "long",
        "position_size": "0.003",
        "entry_price": "86854.137",
        "stop_loss": "86001.234",
        "take_profit": "88555.678",
    }

    with pytest.raises(
        RuntimeError,
        match="Open entry order already exists for BTCUSDT",
    ):
        executor.execute_trade(
            "btcusdt",
            trade_plan,
        )

    assert exchange.calls == []
    assert order_engine.calls == []


def test_execute_trade_runs_entry_then_verification_then_protection():
    events = []

    class WorkflowExchange:
        def get_open_orders(self, symbol=None):
            return []

        def create_order(self, **kwargs):
            events.append("entry")
            return {
                "orderId": "TEST-ORDER-456",
                "orderStatus": "New",
            }

        def get_order(self, symbol, order_id):
            events.append("order_state")
            assert symbol == "BTCUSDT"
            assert order_id == "TEST-ORDER-456"

            return {
                "orderId": "TEST-ORDER-456",
                "orderStatus": "Filled",
            }

        def set_trading_stop(self, **kwargs):
            events.append("protection")
            return {
                "retCode": 0,
                "result": {
                    "status": "OK",
                },
            }

    class WorkflowOrderEngine(FakeOrderEngine):
        def prepare_protection_orders(self, symbol, trade_plan):
            events.append("prepare_protection")

            return {
                "category": "linear",
                "symbol": symbol,
                "tpslMode": "Full",
                "positionIdx": 0,
                "stopLoss": "86001.20",
                "takeProfit": "88555.60",
                "slTriggerBy": "MarkPrice",
                "tpTriggerBy": "MarkPrice",
            }

    class WorkflowPositionManager(FakePositionManager):
        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            events.append("verification")

            return {
                "symbol": symbol.upper(),
                "status": "MATCH",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": "Buy",
                "actual_size": 0.003,
                "actual_entry_price": 86854.10,
                "actual_unrealized_pnl": 0.0,
            }

        def get_protection_state(self, symbol):
            events.append("protection_verification")

            return {
                "symbol": symbol.upper(),
                "has_position": True,
                "has_stop_loss": True,
                "has_take_profit": True,
                "stop_loss": 86001.20,
                "take_profit": 88555.60,
            }

    executor = TradeExecutor(
        exchange=WorkflowExchange(),
        order_engine=WorkflowOrderEngine(),
        position_manager=WorkflowPositionManager(False),
    )

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
        "direction": "long",
        "position_size": "0.003",
        "entry_price": "86854.137",
        "stop_loss": "86001.234",
        "take_profit": "88555.678",
    }

    result = executor.execute_trade(
        "btcusdt",
        trade_plan,
    )

    assert result["entry"]["orderStatus"] == "New"
    assert result["order_state"]["state"] == "FILLED"
    assert result["order_state"]["raw_status"] == "Filled"
    assert result["verification"]["status"] == "MATCH"
    assert result["protection"]["retCode"] == 0

    assert events == [
        "entry",
        "order_state",
        "verification",
        "prepare_protection",
        "protection",
        "protection_verification",
    ]


def test_execute_trade_does_not_apply_protection_when_position_is_missing():
    events = []

    class SafetyExchange:
        def get_open_orders(self, symbol=None):
            return []

        def create_order(self, **kwargs):
            events.append("entry")
            return {
                "orderId": "TEST-ORDER-789",
                "orderStatus": "New",
            }

        def get_order(self, symbol, order_id):
            return {
                "orderId": order_id,
                "orderStatus": "Filled",
            }

        def set_trading_stop(self, **kwargs):
            events.append("protection")
            raise AssertionError(
                "Protection must not be applied without a verified position."
            )

    class SafetyOrderEngine(FakeOrderEngine):
        def prepare_protection_orders(self, symbol, trade_plan):
            events.append("prepare_protection")
            raise AssertionError(
                "Protection must not even be prepared without a verified position."
            )

    class SafetyPositionManager(FakePositionManager):
        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            events.append("verification")

            return {
                "symbol": symbol.upper(),
                "status": "MISSING_POSITION",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": None,
                "actual_size": 0.0,
                "actual_entry_price": 0.0,
                "actual_unrealized_pnl": 0.0,
            }

    executor = TradeExecutor(
        exchange=SafetyExchange(),
        order_engine=SafetyOrderEngine(),
        position_manager=SafetyPositionManager(False),
    )

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
        "direction": "long",
        "position_size": "0.003",
        "entry_price": "86854.137",
        "stop_loss": "86001.234",
        "take_profit": "88555.678",
    }

    try:
        executor.execute_trade(
            "btcusdt",
            trade_plan,
        )
    except RuntimeError as exc:
        assert "Position verification failed" in str(exc)
    else:
        raise AssertionError(
            "execute_trade() must reject an unverified position."
        )

    assert events == [
        "entry",
        "verification",
    ]


def test_execute_trade_does_not_apply_protection_when_position_mismatches():
    events = []

    class MismatchExchange:
        def get_open_orders(self, symbol=None):
            return []

        def create_order(self, **kwargs):
            events.append("entry")
            return {
                "orderId": "TEST-ORDER-MISMATCH",
                "orderStatus": "New",
            }

        def get_order(self, symbol, order_id):
            return {
                "orderId": "TEST-ORDER-MISMATCH",
                "orderStatus": "Filled",
            }

        def set_trading_stop(self, **kwargs):
            events.append("protection")
            raise AssertionError(
                "Protection must not be applied to a mismatched position."
            )

    class MismatchOrderEngine(FakeOrderEngine):
        def prepare_protection_orders(self, symbol, trade_plan):
            events.append("prepare_protection")
            raise AssertionError(
                "Protection must not even be prepared for a mismatched position."
            )

    class MismatchPositionManager(FakePositionManager):
        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            events.append("verification")

            return {
                "symbol": symbol.upper(),
                "status": "POSITION_MISMATCH",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": "Sell",
                "actual_size": 0.003,
                "actual_entry_price": 86854.10,
                "actual_unrealized_pnl": 0.0,
            }

    executor = TradeExecutor(
        exchange=MismatchExchange(),
        order_engine=MismatchOrderEngine(),
        position_manager=MismatchPositionManager(False),
    )

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
        "direction": "long",
        "position_size": "0.003",
        "entry_price": "86854.137",
        "stop_loss": "86001.234",
        "take_profit": "88555.678",
    }

    try:
        executor.execute_trade(
            "btcusdt",
            trade_plan,
        )
    except RuntimeError as exc:
        assert "Position verification failed" in str(exc)
    else:
        raise AssertionError(
            "execute_trade() must reject a mismatched position."
        )

    assert events == [
        "entry",
        "verification",
    ]


def test_execute_trade_records_position_verification_failure():
    class VerificationFailureExchange:
        def get_open_orders(self, symbol=None):
            return []

        def create_order(self, **kwargs):
            return {
                "orderId": "TEST-ORDER-VERIFICATION-FAIL",
                "orderStatus": "New",
            }

        def get_order(self, symbol, order_id):
            return {
                "orderId": order_id,
                "orderStatus": "Filled",
            }

        def set_trading_stop(self, **kwargs):
            raise AssertionError(
                "Protection must not be applied after failed position verification."
            )

    class VerificationFailureOrderEngine(FakeOrderEngine):
        def prepare_protection_orders(self, symbol, trade_plan):
            raise AssertionError(
                "Protection must not be prepared after failed position verification."
            )

    class VerificationFailurePositionManager(FakePositionManager):
        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            return {
                "symbol": symbol.upper(),
                "status": "SIZE_MISMATCH",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": "Buy",
                "actual_size": 0.002,
                "actual_entry_price": 86854.10,
                "actual_unrealized_pnl": 0.0,
            }

    class RecordingTradeExecutor(TradeExecutor):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.record = None

        def create_trade_record(self, symbol, order_id=None):
            self.record = super().create_trade_record(
                symbol,
                order_id,
            )
            return self.record

    executor = RecordingTradeExecutor(
        exchange=VerificationFailureExchange(),
        order_engine=VerificationFailureOrderEngine(),
        position_manager=VerificationFailurePositionManager(False),
    )

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
        "direction": "long",
        "position_size": "0.003",
        "entry_price": "86854.137",
        "stop_loss": "86001.234",
        "take_profit": "88555.678",
    }

    try:
        executor.execute_trade(
            "btcusdt",
            trade_plan,
        )
    except RuntimeError as exc:
        assert "Position verification failed" in str(exc)
    else:
        raise AssertionError(
            "execute_trade() must reject failed position verification."
        )

    assert executor.record is not None
    assert executor.record.state == "POSITION_VERIFICATION_FAILED"


def test_execute_trade_reports_protection_failure_after_verified_fill():
    events = []

    class ProtectionFailureExchange:
        def get_open_orders(self, symbol=None):
            return []

        def create_order(self, **kwargs):
            events.append("entry")
            return {
                "orderId": "TEST-ORDER-PROTECTION-FAIL",
                "orderStatus": "Filled",
            }

        def get_order(self, symbol, order_id):
            return {
                "orderId": order_id,
                "orderStatus": "Filled",
            }

        def set_trading_stop(self, **kwargs):
            events.append("protection")
            raise RuntimeError("Bybit protection request failed.")

    class ProtectionFailureOrderEngine(FakeOrderEngine):
        def prepare_protection_orders(self, symbol, trade_plan):
            events.append("prepare_protection")

            return {
                "category": "linear",
                "symbol": symbol.upper(),
                "tpslMode": "Full",
                "positionIdx": 0,
                "stopLoss": "86001.20",
                "takeProfit": "88555.60",
                "slTriggerBy": "MarkPrice",
                "tpTriggerBy": "MarkPrice",
            }

    class ProtectionFailurePositionManager(FakePositionManager):
        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            events.append("verification")

            return {
                "symbol": symbol.upper(),
                "status": "MATCH",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": "Buy",
                "actual_size": 0.003,
                "actual_entry_price": 86854.10,
                "actual_unrealized_pnl": 0.0,
            }

        def get_position(self, symbol):
            return {
                "symbol": symbol.upper(),
                "side": "Buy",
                "size": "0.003",
                "avgPrice": "86854.10",
                "unrealisedPnl": "0",
            }

        def get_protection_state(self, symbol):
            return {
                "symbol": symbol.upper(),
                "has_position": True,
                "has_stop_loss": False,
                "has_take_profit": False,
                "stop_loss": None,
                "take_profit": None,
            }

    executor = TradeExecutor(
        exchange=ProtectionFailureExchange(),
        order_engine=ProtectionFailureOrderEngine(),
        position_manager=ProtectionFailurePositionManager(False),
    )

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
        "direction": "long",
        "position_size": "0.003",
        "entry_price": "86854.137",
        "stop_loss": "86001.234",
        "take_profit": "88555.678",
    }

    try:
        executor.execute_trade(
            "btcusdt",
            trade_plan,
        )
    except RuntimeError as exc:
        assert "protection" in str(exc).lower()
    else:
        raise AssertionError(
            "execute_trade() must surface protection failure."
        )

    assert events == [
        "entry",
        "verification",
        "prepare_protection",
        "protection",
        "verification",
        "prepare_protection",
        "protection",
    ]


def test_execute_trade_stops_when_entry_submission_fails():
    events = []

    class EntryFailureExchange:
        def get_open_orders(self, symbol=None):
            return []

        def create_order(self, **kwargs):
            events.append("entry")
            raise RuntimeError("Bybit entry order failed.")

        def set_trading_stop(self, **kwargs):
            events.append("protection")
            raise AssertionError(
                "Protection must never be attempted after entry failure."
            )

    class EntryFailureOrderEngine(FakeOrderEngine):
        def prepare_protection_orders(self, symbol, trade_plan):
            events.append("prepare_protection")
            raise AssertionError(
                "Protection must never be prepared after entry failure."
            )

    class EntryFailurePositionManager(FakePositionManager):
        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            events.append("verification")
            raise AssertionError(
                "Position verification must not run after entry failure."
            )

    executor = TradeExecutor(
        exchange=EntryFailureExchange(),
        order_engine=EntryFailureOrderEngine(),
        position_manager=EntryFailurePositionManager(False),
    )

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
        "direction": "long",
        "position_size": "0.003",
        "entry_price": "86854.137",
        "stop_loss": "86001.234",
        "take_profit": "88555.678",
    }

    try:
        executor.execute_trade(
            "btcusdt",
            trade_plan,
        )
    except RuntimeError as exc:
        assert "entry" in str(exc).lower()
    else:
        raise AssertionError(
            "execute_trade() must surface entry failure."
        )

    assert events == [
        "entry",
    ]


def test_execute_trade_marks_verified_position_unprotected_when_protection_fails():
    class UnprotectedExchange:
        def get_open_orders(self, symbol=None):
            return []

        def create_order(self, **kwargs):
            return {
                "orderId": "TEST-UNPROTECTED-001",
                "orderStatus": "Filled",
            }

        def get_order(self, symbol, order_id):
            return {
                "orderId": order_id,
                "orderStatus": "Filled",
            }

        def set_trading_stop(self, **kwargs):
            raise RuntimeError("Protection endpoint unavailable.")

    class UnprotectedOrderEngine(FakeOrderEngine):
        def prepare_protection_orders(self, symbol, trade_plan):
            return {
                "category": "linear",
                "symbol": symbol.upper(),
                "tpslMode": "Full",
                "positionIdx": 0,
                "stopLoss": "86001.20",
                "takeProfit": "88555.60",
                "slTriggerBy": "MarkPrice",
                "tpTriggerBy": "MarkPrice",
            }

    class UnprotectedPositionManager(FakePositionManager):
        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            return {
                "symbol": symbol.upper(),
                "status": "MATCH",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": "Buy",
                "actual_size": 0.003,
                "actual_entry_price": 86854.10,
                "actual_unrealized_pnl": 0.0,
            }

        def get_position(self, symbol):
            return {
                "symbol": symbol.upper(),
                "side": "Buy",
                "size": "0.003",
                "avgPrice": "86854.10",
                "unrealisedPnl": "0",
            }

        def get_protection_state(self, symbol):
            return {
                "symbol": symbol.upper(),
                "has_position": True,
                "has_stop_loss": False,
                "has_take_profit": False,
                "stop_loss": None,
                "take_profit": None,
            }

    executor = TradeExecutor(
        exchange=UnprotectedExchange(),
        order_engine=UnprotectedOrderEngine(),
        position_manager=UnprotectedPositionManager(False),
    )

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
        "direction": "long",
        "position_size": "0.003",
        "entry_price": "86854.137",
        "stop_loss": "86001.234",
        "take_profit": "88555.678",
    }

    try:
        executor.execute_trade(
            "btcusdt",
            trade_plan,
        )
    except RuntimeError as exc:
        message = str(exc).lower()
        assert "unprotected" in message
    else:
        raise AssertionError(
            "A verified position with failed protection must be "
            "reported as unprotected."
        )


def test_protection_failure_returns_retry_protection_recovery_action():
    class RecoveryExchange:
        def get_open_orders(self, symbol=None):
            return []

        def create_order(self, **kwargs):
            return {
                "orderId": "TEST-RECOVERY-001",
                "orderStatus": "Filled",
            }

        def get_order(self, symbol, order_id):
            return {
                "orderId": order_id,
                "orderStatus": "Filled",
            }

        def set_trading_stop(self, **kwargs):
            raise RuntimeError("Protection endpoint temporarily unavailable.")

    class RecoveryOrderEngine(FakeOrderEngine):
        def prepare_protection_orders(self, symbol, trade_plan):
            return {
                "category": "linear",
                "symbol": symbol.upper(),
                "tpslMode": "Full",
                "positionIdx": 0,
                "stopLoss": "86001.20",
                "takeProfit": "88555.60",
                "slTriggerBy": "MarkPrice",
                "tpTriggerBy": "MarkPrice",
            }

    class RecoveryPositionManager(FakePositionManager):
        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            return {
                "symbol": symbol.upper(),
                "status": "MATCH",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": "Buy",
                "actual_size": 0.003,
                "actual_entry_price": 86854.10,
                "actual_unrealized_pnl": 0.0,
            }

        def get_position(self, symbol):
            return {
                "symbol": symbol.upper(),
                "side": "Buy",
                "size": "0.003",
                "avgPrice": "86854.10",
                "unrealisedPnl": "0",
            }

        def get_protection_state(self, symbol):
            return {
                "symbol": symbol.upper(),
                "has_position": True,
                "has_stop_loss": False,
                "has_take_profit": False,
                "stop_loss": None,
                "take_profit": None,
            }

    executor = TradeExecutor(
        exchange=RecoveryExchange(),
        order_engine=RecoveryOrderEngine(),
        position_manager=RecoveryPositionManager(False),
    )

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
        "direction": "long",
        "position_size": "0.003",
        "entry_price": "86854.137",
        "stop_loss": "86001.234",
        "take_profit": "88555.678",
    }

    try:
        executor.execute_trade(
            "btcusdt",
            trade_plan,
        )
    except RuntimeError as exc:
        message = str(exc)

        assert "POSITION_ACTIVE_UNPROTECTED" in message
        assert "recovery_status=RECOVERY_FAILED" in message
    else:
        raise AssertionError(
            "Protection failure must produce a recovery action."
        )


def test_submit_entry_blocks_when_kill_switch_is_active():
    from safety.kill_switch import KillSwitch

    class FakeExchange:
        def create_order(self, **kwargs):
            raise AssertionError("Exchange entry must not be called.")

    class FakeOrderEngine:
        def prepare_order(self, symbol, trade_plan):
            raise AssertionError("Order preparation must not be called.")

    class FakePositionManager:
        def has_position(self, symbol):
            raise AssertionError("Position check must not be called.")

    kill_switch = KillSwitch()
    kill_switch.activate("Emergency safety stop")

    executor = TradeExecutor(
        FakeExchange(),
        FakeOrderEngine(),
        FakePositionManager(),
        kill_switch=kill_switch,
    )

    with pytest.raises(RuntimeError, match="KILL_SWITCH_ACTIVE"):
        executor.submit_entry(
            "BTCUSDT",
            {"status": "GUARDIAN_APPROVED"},
        )


def test_unhealthy_exchange_chain_blocks_trade_execution():
    from safety.health_monitor import HealthMonitor
    from safety.kill_switch import KillSwitch

    class FakeHealthExchange:
        def get_server_time(self):
            raise RuntimeError("Bybit unavailable")

    class FakeTradeExchange:
        def create_order(self, **kwargs):
            raise AssertionError("Exchange entry must not be called.")

    class FakeOrderEngine:
        def prepare_order(self, symbol, trade_plan):
            raise AssertionError("Order preparation must not be called.")

    class FakePositionManager:
        def has_position(self, symbol):
            raise AssertionError("Position check must not be called.")

    health_monitor = HealthMonitor()
    kill_switch = KillSwitch()

    assert health_monitor.check_exchange_connectivity(
        FakeHealthExchange()
    ) is False

    health_monitor.enforce_kill_switch(kill_switch)

    executor = TradeExecutor(
        FakeTradeExchange(),
        FakeOrderEngine(),
        FakePositionManager(),
        kill_switch=kill_switch,
    )

    with pytest.raises(RuntimeError, match="KILL_SWITCH_ACTIVE"):
        executor.submit_entry(
            "BTCUSDT",
            {"status": "GUARDIAN_APPROVED"},
        )


def test_position_safety_blocks_entry_when_position_is_unsafe():
    from safety.kill_switch import KillSwitch
    from safety.position_safety import PositionSafetyMonitor

    class UnsafePositionManager:
        def has_position(self, symbol):
            raise AssertionError("has_position should not be reached")

        def reconcile_position(self, symbol, expected_side=None, expected_size=0.0):
            return {
                "symbol": symbol,
                "status": "UNEXPECTED_POSITION",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": "Buy",
                "actual_size": 1.0,
                "actual_entry_price": 100000.0,
                "actual_unrealized_pnl": 0.0,
            }

    class NoOrderEngine:
        def prepare_order(self, symbol, trade_plan):
            raise AssertionError("Order preparation should not be reached")

    class NoExchange:
        def create_order(self, **kwargs):
            raise AssertionError("Exchange order submission should not be reached")

    position_manager = UnsafePositionManager()
    kill_switch = KillSwitch()
    position_safety = PositionSafetyMonitor(position_manager)

    executor = TradeExecutor(
        exchange=NoExchange(),
        order_engine=NoOrderEngine(),
        position_manager=position_manager,
        kill_switch=kill_switch,
        position_safety_monitor=position_safety,
    )

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
    }

    with pytest.raises(RuntimeError, match="KILL_SWITCH_ACTIVE"):
        executor.submit_entry("BTCUSDT", trade_plan)

    assert kill_switch.is_active() is True
    assert "UNEXPECTED_POSITION" in kill_switch.reason()


def test_position_safety_allows_clean_entry_preflight():
    from safety.kill_switch import KillSwitch
    from safety.position_safety import PositionSafetyMonitor

    class CleanPositionManager:
        def has_position(self, symbol):
            return False

        def reconcile_position(self, symbol, expected_side=None, expected_size=0.0):
            return {
                "symbol": symbol,
                "status": "MATCH",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": None,
                "actual_size": 0.0,
                "actual_entry_price": 0.0,
                "actual_unrealized_pnl": 0.0,
            }

    class RecordingOrderEngine:
        def __init__(self):
            self.prepared = False

        def prepare_order(self, symbol, trade_plan):
            self.prepared = True
            return {
                "symbol": symbol,
                "side": "Buy",
                "orderType": "Limit",
                "qty": "0.001",
                "price": "80000.00",
            }

    class RecordingExchange:
        def __init__(self):
            self.submitted = False

        def get_open_orders(self, symbol=None):
            return []

        def create_order(self, **kwargs):
            self.submitted = True
            return {"retCode": 0, "orderId": "test-order"}

    position_manager = CleanPositionManager()
    order_engine = RecordingOrderEngine()
    exchange = RecordingExchange()
    kill_switch = KillSwitch()
    position_safety = PositionSafetyMonitor(position_manager)

    executor = TradeExecutor(
        exchange=exchange,
        order_engine=order_engine,
        position_manager=position_manager,
        kill_switch=kill_switch,
        position_safety_monitor=position_safety,
    )

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
    }

    result = executor.submit_entry("BTCUSDT", trade_plan)

    assert result["retCode"] == 0
    assert order_engine.prepared is True
    assert exchange.submitted is True
    assert kill_switch.is_active() is False


def test_get_entry_order_state_returns_filled_state():
    class OrderStateExchange:
        def get_order(self, symbol, order_id):
            assert symbol == "BTCUSDT"
            assert order_id == "ORDER-123"
            return {
                "orderId": "ORDER-123",
                "orderStatus": "Filled",
            }

    executor = TradeExecutor(
        exchange=OrderStateExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=FakePositionManager(),
    )

    result = executor.get_entry_order_state(
        "btcusdt",
        "ORDER-123",
    )

    assert result["order_id"] == "ORDER-123"
    assert result["raw_status"] == "Filled"
    assert result["state"] == "FILLED"
    assert result["order"]["orderId"] == "ORDER-123"


def test_get_entry_order_state_returns_unknown_when_order_missing():
    class MissingOrderExchange:
        def get_order(self, symbol, order_id):
            return None

    executor = TradeExecutor(
        exchange=MissingOrderExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=FakePositionManager(),
    )

    result = executor.get_entry_order_state(
        "BTCUSDT",
        "MISSING-ORDER",
    )

    assert result["order_id"] == "MISSING-ORDER"
    assert result["raw_status"] is None
    assert result["state"] == "UNKNOWN"
    assert result["order"] is None


def test_get_entry_order_state_rejects_missing_order_id():
    executor = TradeExecutor(
        exchange=RecordingExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=FakePositionManager(),
    )

    with pytest.raises(ValueError, match="Order ID is required"):
        executor.get_entry_order_state("BTCUSDT", "")


def test_get_entry_order_state_reads_filled_order_from_exchange():
    class FilledOrderExchange:
        def get_order(self, symbol, order_id):
            assert symbol == "BTCUSDT"
            assert order_id == "TEST-FILLED-001"

            return {
                "orderId": "TEST-FILLED-001",
                "orderStatus": "Filled",
            }

    executor = TradeExecutor(
        exchange=FilledOrderExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=FakePositionManager(),
    )

    result = executor.get_entry_order_state(
        "BTCUSDT",
        "TEST-FILLED-001",
    )

    assert result == {
        "order_id": "TEST-FILLED-001",
        "raw_status": "Filled",
        "state": "FILLED",
        "order": {
            "orderId": "TEST-FILLED-001",
            "orderStatus": "Filled",
        },
    }


def test_execute_trade_stops_when_entry_order_is_not_filled():
    events = []

    class PendingExchange:
        def get_open_orders(self, symbol=None):
            return []

        def create_order(self, **kwargs):
            events.append("entry")
            return {
                "orderId": "TEST-PENDING-001",
                "orderStatus": "New",
            }

        def get_order(self, symbol, order_id):
            events.append("order_state")
            return {
                "orderId": "TEST-PENDING-001",
                "orderStatus": "New",
            }

        def set_trading_stop(self, **kwargs):
            events.append("protection")
            raise AssertionError(
                "TP/SL must not be applied to a non-filled entry."
            )

    class PendingPositionManager(FakePositionManager):
        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            events.append("verification")
            raise AssertionError(
                "Position verification must not run before entry fill."
            )

    executor = TradeExecutor(
        exchange=PendingExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=PendingPositionManager(False),
    )

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
        "direction": "long",
        "position_size": "0.003",
        "entry_price": "86854.137",
        "stop_loss": "86001.234",
        "take_profit": "88555.678",
    }

    result = executor.execute_trade(
        "BTCUSDT",
        trade_plan,
    )

    assert result["order_state"]["state"] == "PENDING"
    assert result["status"] == "ENTRY_PENDING"
    assert events == [
        "entry",
        "order_state",
    ]


def test_execute_trade_stops_on_partially_filled_entry():
    events = []

    class PartialExchange:
        def get_open_orders(self, symbol=None):
            return []

        def create_order(self, **kwargs):
            events.append("entry")
            return {"orderId": "TEST-PARTIAL-001", "orderStatus": "New"}

        def get_order(self, symbol, order_id):
            events.append("order_state")
            return {
                "orderId": "TEST-PARTIAL-001",
                "orderStatus": "PartiallyFilled",
            }

    class PartialPositionManager(FakePositionManager):
        def reconcile_position(self, *args, **kwargs):
            events.append("verification")
            raise AssertionError("Position verification must not run.")

    executor = TradeExecutor(
        exchange=PartialExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=PartialPositionManager(False),
    )

    result = executor.execute_trade(
        "BTCUSDT",
        {
            "status": "GUARDIAN_APPROVED",
            "direction": "long",
            "position_size": "0.003",
            "entry_price": "86854.137",
            "stop_loss": "86001.234",
            "take_profit": "88555.678",
        },
    )

    assert result["order_state"]["state"] == "PARTIALLY_FILLED"
    assert result["status"] == "ENTRY_PARTIALLY_FILLED"
    assert events == ["entry", "order_state"]


def test_execute_trade_stops_on_cancelled_entry():
    events = []

    class CancelledExchange:
        def get_open_orders(self, symbol=None):
            return []

        def create_order(self, **kwargs):
            events.append("entry")
            return {"orderId": "TEST-CANCELLED-001", "orderStatus": "New"}

        def get_order(self, symbol, order_id):
            events.append("order_state")
            return {
                "orderId": "TEST-CANCELLED-001",
                "orderStatus": "Cancelled",
            }

    class CancelledPositionManager(FakePositionManager):
        def reconcile_position(self, *args, **kwargs):
            events.append("verification")
            raise AssertionError("Position verification must not run.")

    executor = TradeExecutor(
        exchange=CancelledExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=CancelledPositionManager(False),
    )

    result = executor.execute_trade(
        "BTCUSDT",
        {
            "status": "GUARDIAN_APPROVED",
            "direction": "long",
            "position_size": "0.003",
            "entry_price": "86854.137",
            "stop_loss": "86001.234",
            "take_profit": "88555.678",
        },
    )

    assert result["order_state"]["state"] == "CANCELLED"
    assert result["status"] == "ENTRY_CANCELLED"
    assert events == ["entry", "order_state"]


def test_execute_trade_stops_on_rejected_entry():
    events = []

    class RejectedExchange:
        def get_open_orders(self, symbol=None):
            return []

        def create_order(self, **kwargs):
            events.append("entry")
            return {"orderId": "TEST-REJECTED-001", "orderStatus": "New"}

        def get_order(self, symbol, order_id):
            events.append("order_state")
            return {
                "orderId": "TEST-REJECTED-001",
                "orderStatus": "Rejected",
            }

    class RejectedPositionManager(FakePositionManager):
        def reconcile_position(self, *args, **kwargs):
            events.append("verification")
            raise AssertionError("Position verification must not run.")

    executor = TradeExecutor(
        exchange=RejectedExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=RejectedPositionManager(False),
    )

    result = executor.execute_trade(
        "BTCUSDT",
        {
            "status": "GUARDIAN_APPROVED",
            "direction": "long",
            "position_size": "0.003",
            "entry_price": "86854.137",
            "stop_loss": "86001.234",
            "take_profit": "88555.678",
        },
    )

    assert result["order_state"]["state"] == "REJECTED"
    assert result["status"] == "ENTRY_REJECTED"
    assert events == ["entry", "order_state"]


def test_execute_trade_stops_on_unknown_entry_state():
    events = []

    class UnknownExchange:
        def get_open_orders(self, symbol=None):
            return []

        def create_order(self, **kwargs):
            events.append("entry")
            return {"orderId": "TEST-UNKNOWN-001", "orderStatus": "New"}

        def get_order(self, symbol, order_id):
            events.append("order_state")
            return {
                "orderId": "TEST-UNKNOWN-001",
                "orderStatus": "SomethingUnexpected",
            }

    class UnknownPositionManager(FakePositionManager):
        def reconcile_position(self, *args, **kwargs):
            events.append("verification")
            raise AssertionError("Position verification must not run.")

    executor = TradeExecutor(
        exchange=UnknownExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=UnknownPositionManager(False),
    )

    result = executor.execute_trade(
        "BTCUSDT",
        {
            "status": "GUARDIAN_APPROVED",
            "direction": "long",
            "position_size": "0.003",
            "entry_price": "86854.137",
            "stop_loss": "86001.234",
            "take_profit": "88555.678",
        },
    )

    assert result["order_state"]["state"] == "UNKNOWN"
    assert result["status"] == "ENTRY_STATE_UNKNOWN"
    assert events == ["entry", "order_state"]

def test_get_entry_order_state_includes_execution_data():
    class ExecutionDataExchange:
        def get_order(self, symbol, order_id):
            return {
                "orderId": order_id,
                "orderStatus": "PartiallyFilled",
                "qty": "0.003",
                "cumExecQty": "0.001",
                "leavesQty": "0.002",
                "avgPrice": "86854.10",
            }

    executor = TradeExecutor(
        exchange=ExecutionDataExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=FakePositionManager(),
    )

    result = executor.get_entry_order_state(
        "BTCUSDT",
        "TEST-EXECUTION-001",
    )

    assert result["state"] == "PARTIALLY_FILLED"
    assert result["execution"] == {
        "order_quantity": 0.003,
        "filled_quantity": 0.001,
        "remaining_quantity": 0.002,
        "average_fill_price": 86854.10,
    }


def test_trade_executor_can_create_trade_record():
    from execution.trade_record import TradeRecord

    record = TradeRecord(
        symbol="BTCUSDT",
        order_id="test-order-123",
    )

    assert isinstance(record, TradeRecord)
    assert record.symbol == "BTCUSDT"
    assert record.order_id == "test-order-123"
    assert record.state == "CREATED"


def test_trade_executor_create_trade_record():
    from execution.trade_executor import TradeExecutor
    from execution.trade_record import TradeRecord

    executor = TradeExecutor(
        exchange=None,
        order_engine=None,
        position_manager=None,
    )

    record = executor.create_trade_record(
        "btcusdt",
        order_id="test-order-456",
    )

    assert isinstance(record, TradeRecord)
    assert record.symbol == "BTCUSDT"
    assert record.order_id == "test-order-456"
    assert record.state == "CREATED"


def test_trade_executor_records_pending_entry_state():
    from execution.trade_executor import TradeExecutor

    class FakeExchange:
        def get_open_orders(self, symbol):
            return []

        def get_position(self, symbol):
            return None

        def create_order(self, **kwargs):
            return {"orderId": "pending-123"}

        def get_order(self, symbol, order_id):
            return {
                "orderId": order_id,
                "orderStatus": "New",
            }

    class FakeOrderEngine:
        def prepare_order(self, symbol, trade_plan):
            return {
                "category": "linear",
                "symbol": symbol.upper(),
                "side": "Buy",
                "orderType": "Limit",
                "qty": "0.001",
                "price": "50000",
            }

    class FakePositionManager:
        def has_position(self, symbol):
            return False

        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            return {
                "symbol": symbol,
                "status": "MATCH",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": None,
                "actual_size": 0.0,
                "actual_entry_price": 0.0,
                "actual_unrealized_pnl": 0.0,
            }

    executor = TradeExecutor(
        exchange=FakeExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=FakePositionManager(),
    )

    result = executor.execute_trade(
        "BTCUSDT",
        {
            "status": "GUARDIAN_APPROVED",
        },
    )

    assert result["status"] == "ENTRY_PENDING"
    assert result["trade_record"]["symbol"] == "BTCUSDT"
    assert result["trade_record"]["order_id"] == "pending-123"
    assert result["trade_record"]["state"] == "ENTRY_PENDING"


def test_trade_executor_records_successful_trade_lifecycle():
    from execution.trade_executor import TradeExecutor

    class FakeExchange:
        def get_open_orders(self, symbol):
            return []

        def get_position(self, symbol):
            return {
                "symbol": symbol,
                "side": "Buy",
                "size": "0.001",
                "avgPrice": "50000",
                "unrealisedPnl": "0",
            }

        def create_order(self, **kwargs):
            return {"orderId": "filled-123"}

        def get_order(self, symbol, order_id):
            return {
                "orderId": order_id,
                "orderStatus": "Filled",
                "qty": "0.001",
                "cumExecQty": "0.001",
                "leavesQty": "0",
                "avgPrice": "50000",
            }

        def set_trading_stop(self, **kwargs):
            return {
                "retCode": 0,
                "result": {},
            }

    class FakeOrderEngine:
        def prepare_order(self, symbol, trade_plan):
            return {
                "category": "linear",
                "symbol": symbol.upper(),
                "side": "Buy",
                "orderType": "Limit",
                "qty": "0.001",
                "price": "50000",
            }

        def prepare_protection_orders(self, symbol, trade_plan):
            return {
                "category": "linear",
                "symbol": symbol.upper(),
                "tpslMode": "Full",
                "positionIdx": 0,
                "stopLoss": "49000",
                "takeProfit": "52000",
                "slTriggerBy": "MarkPrice",
                "tpTriggerBy": "MarkPrice",
            }

    class FakePositionManager:
        def has_position(self, symbol):
            return False

        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            return {
                "symbol": symbol,
                "status": "MATCH",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": expected_side,
                "actual_size": expected_size,
                "actual_entry_price": 50000.0,
                "actual_unrealized_pnl": 0.0,
            }

        def get_protection_state(self, symbol):
            return {
                "symbol": symbol.upper(),
                "has_position": True,
                "has_stop_loss": True,
                "has_take_profit": True,
                "stop_loss": 49000.0,
                "take_profit": 52000.0,
            }

    executor = TradeExecutor(
        exchange=FakeExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=FakePositionManager(),
    )

    result = executor.execute_trade(
        "BTCUSDT",
        {
            "status": "GUARDIAN_APPROVED",
        },
    )

    record = result["trade_record"]

    assert record["symbol"] == "BTCUSDT"
    assert record["order_id"] == "filled-123"
    assert record["state"] == "PROTECTION_APPLIED"
    assert record["order_quantity"] == 0.001
    assert record["filled_quantity"] == 0.001
    assert record["remaining_quantity"] == 0.0
    assert record["average_fill_price"] == 50000.0


def test_trade_executor_records_protection_failure():
    import pytest
    from execution.trade_executor import TradeExecutor

    class FakeExchange:
        def get_open_orders(self, symbol):
            return []

        def get_position(self, symbol):
            return {
                "symbol": symbol,
                "side": "Buy",
                "size": "0.001",
                "avgPrice": "50000",
                "unrealisedPnl": "0",
            }

        def create_order(self, **kwargs):
            return {"orderId": "protection-fail-123"}

        def get_order(self, symbol, order_id):
            return {
                "orderId": order_id,
                "orderStatus": "Filled",
                "qty": "0.001",
                "cumExecQty": "0.001",
                "leavesQty": "0",
                "avgPrice": "50000",
            }

        def set_trading_stop(self, **kwargs):
            raise RuntimeError("simulated TP/SL failure")

    class FakeOrderEngine:
        def prepare_order(self, symbol, trade_plan):
            return {
                "category": "linear",
                "symbol": symbol.upper(),
                "side": "Buy",
                "orderType": "Limit",
                "qty": "0.001",
                "price": "50000",
            }

        def prepare_protection_orders(self, symbol, trade_plan):
            return {
                "category": "linear",
                "symbol": symbol.upper(),
                "tpslMode": "Full",
                "positionIdx": 0,
                "stopLoss": "49000",
                "takeProfit": "52000",
                "slTriggerBy": "MarkPrice",
                "tpTriggerBy": "MarkPrice",
            }

    class FakePositionManager:
        def has_position(self, symbol):
            return False

        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            return {
                "symbol": symbol,
                "status": "MATCH",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": expected_side,
                "actual_size": expected_size,
                "actual_entry_price": 50000.0,
                "actual_unrealized_pnl": 0.0,
            }

        def get_protection_state(self, symbol):
            return {
                "symbol": symbol.upper(),
                "has_position": True,
                "has_stop_loss": False,
                "has_take_profit": False,
                "stop_loss": None,
                "take_profit": None,
            }

    executor = TradeExecutor(
        exchange=FakeExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=FakePositionManager(),
    )

    with pytest.raises(RuntimeError, match="POSITION_ACTIVE_UNPROTECTED"):
        executor.execute_trade(
            "BTCUSDT",
            {
                "status": "GUARDIAN_APPROVED",
            },
        )


def test_execute_trade_verifies_protection_after_application():
    events = []

    class ProtectionVerifiedExchange:
        def get_open_orders(self, symbol=None):
            return []

        def create_order(self, **kwargs):
            events.append("entry")
            return {
                "orderId": "TEST-ORDER-PROTECTION-VERIFIED",
                "orderStatus": "Filled",
            }

        def get_order(self, symbol, order_id):
            events.append("order_state")
            return {
                "orderId": order_id,
                "orderStatus": "Filled",
            }

        def set_trading_stop(self, **kwargs):
            events.append("protection")
            return {
                "retCode": 0,
                "result": {
                    "status": "OK",
                },
            }

    class ProtectionVerifiedOrderEngine(FakeOrderEngine):
        def prepare_protection_orders(self, symbol, trade_plan):
            events.append("prepare_protection")

            return {
                "category": "linear",
                "symbol": symbol,
                "tpslMode": "Full",
                "positionIdx": 0,
                "stopLoss": "86001.20",
                "takeProfit": "88555.60",
                "slTriggerBy": "MarkPrice",
                "tpTriggerBy": "MarkPrice",
            }

    class ProtectionVerifiedPositionManager(FakePositionManager):
        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            events.append("verification")

            return {
                "symbol": symbol.upper(),
                "status": "MATCH",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": "Buy",
                "actual_size": 0.003,
                "actual_entry_price": 86854.10,
                "actual_unrealized_pnl": 0.0,
            }

        def get_protection_state(self, symbol):
            events.append("protection_verification")

            return {
                "symbol": symbol.upper(),
                "has_position": True,
                "has_stop_loss": True,
                "has_take_profit": True,
                "stop_loss": 86001.20,
                "take_profit": 88555.60,
            }

    exchange = ProtectionVerifiedExchange()
    position_manager = ProtectionVerifiedPositionManager(False)

    executor = TradeExecutor(
        exchange=exchange,
        order_engine=ProtectionVerifiedOrderEngine(),
        position_manager=position_manager,
    )

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
        "direction": "long",
        "position_size": "0.003",
        "entry_price": "86854.137",
        "stop_loss": "86001.234",
        "take_profit": "88555.678",
    }

    result = executor.execute_trade(
        "btcusdt",
        trade_plan,
    )

    assert result["status"] == "PROTECTED"
    assert result["protection_verification"]["status"] == "MATCH"
    assert result["protection_verification"]["safe"] is True

    assert events == [
        "entry",
        "order_state",
        "verification",
        "prepare_protection",
        "protection",
        "protection_verification",
    ]


def test_execute_trade_evaluates_protection_recovery_without_retry():
    import pytest
    from execution.trade_executor import TradeExecutor

    events = []

    class FakeExchange:
        def get_open_orders(self, symbol):
            return []

        def get_position(self, symbol):
            return {
                "symbol": symbol,
                "side": "Buy",
                "size": "0.001",
                "avgPrice": "50000",
                "unrealisedPnl": "0",
            }

        def create_order(self, **kwargs):
            events.append("entry")
            return {"orderId": "recovery-123"}

        def get_order(self, symbol, order_id):
            events.append("order_state")
            return {
                "orderId": order_id,
                "orderStatus": "Filled",
                "qty": "0.001",
                "cumExecQty": "0.001",
                "leavesQty": "0",
                "avgPrice": "50000",
            }

        def set_trading_stop(self, **kwargs):
            events.append("protection")
            return {
                "retCode": 0,
                "result": {},
            }

    class FakeOrderEngine:
        def prepare_order(self, symbol, trade_plan):
            return {
                "category": "linear",
                "symbol": symbol.upper(),
                "side": "Buy",
                "orderType": "Limit",
                "qty": "0.001",
                "price": "50000",
            }

        def prepare_protection_orders(self, symbol, trade_plan):
            events.append("prepare_protection")

            return {
                "category": "linear",
                "symbol": symbol.upper(),
                "tpslMode": "Full",
                "positionIdx": 0,
                "stopLoss": "49000",
                "takeProfit": "52000",
                "slTriggerBy": "MarkPrice",
                "tpTriggerBy": "MarkPrice",
            }

    class FakePositionManager:
        def has_position(self, symbol):
            return False

        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            events.append("position_verification")

            return {
                "symbol": symbol,
                "status": "MATCH",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": "Buy",
                "actual_size": 0.001,
                "actual_entry_price": 50000.0,
                "actual_unrealized_pnl": 0.0,
            }

        def get_protection_state(self, symbol):
            events.append("protection_state")

            return {
                "symbol": symbol.upper(),
                "has_position": True,
                "has_stop_loss": True,
                "has_take_profit": True,
                "stop_loss": 48900.0,
                "take_profit": 52000.0,
            }

    class FakeProtectionRecovery:
        def evaluate(
            self,
            symbol,
            expected_stop_loss,
            expected_take_profit,
        ):
            events.append("recovery_evaluation")

            return {
                "symbol": symbol.upper(),
                "status": "PROTECTION_MISMATCH",
                "safe": False,
                "recovery_required": True,
                "action": "REAPPLY_PROTECTION",
                "reason": "Exchange TP/SL does not match intended protection.",
            }

    executor = TradeExecutor(
        exchange=FakeExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=FakePositionManager(),
        protection_recovery=FakeProtectionRecovery(),
    )

    with pytest.raises(
        RuntimeError,
        match="recovery_status=RECOVERY_FAILED",
    ):
        executor.execute_trade(
            "BTCUSDT",
            {
                "status": "GUARDIAN_APPROVED",
            },
        )

    assert events == [
        "entry",
        "order_state",
        "position_verification",
        "prepare_protection",
        "protection",
        "protection_state",
        "recovery_evaluation",
        "position_verification",
        "prepare_protection",
        "protection",
        "protection_state",
    ]

    assert events.count("protection") == 2


def test_execute_trade_rejects_protection_mismatch_after_application():
    import pytest
    from execution.trade_executor import TradeExecutor

    class FakeExchange:
        def get_open_orders(self, symbol):
            return []

        def get_position(self, symbol):
            return {
                "symbol": symbol,
                "side": "Buy",
                "size": "0.001",
                "avgPrice": "50000",
                "unrealisedPnl": "0",
            }

        def create_order(self, **kwargs):
            return {"orderId": "mismatch-123"}

        def get_order(self, symbol, order_id):
            return {
                "orderId": order_id,
                "orderStatus": "Filled",
                "qty": "0.001",
                "cumExecQty": "0.001",
                "leavesQty": "0",
                "avgPrice": "50000",
            }

        def set_trading_stop(self, **kwargs):
            return {
                "retCode": 0,
                "result": {},
            }

    class FakeOrderEngine:
        def prepare_order(self, symbol, trade_plan):
            return {
                "category": "linear",
                "symbol": symbol.upper(),
                "side": "Buy",
                "orderType": "Limit",
                "qty": "0.001",
                "price": "50000",
            }

        def prepare_protection_orders(self, symbol, trade_plan):
            return {
                "category": "linear",
                "symbol": symbol.upper(),
                "tpslMode": "Full",
                "positionIdx": 0,
                "stopLoss": "49000",
                "takeProfit": "52000",
                "slTriggerBy": "MarkPrice",
                "tpTriggerBy": "MarkPrice",
            }

    class FakePositionManager:
        def has_position(self, symbol):
            return False

        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            return {
                "symbol": symbol,
                "status": "MATCH",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": expected_side,
                "actual_size": expected_size,
                "actual_entry_price": 50000.0,
                "actual_unrealized_pnl": 0.0,
            }

        def get_protection_state(self, symbol):
            return {
                "symbol": symbol.upper(),
                "has_position": True,
                "has_stop_loss": True,
                "has_take_profit": True,
                "stop_loss": 48900.0,
                "take_profit": 52000.0,
            }

    executor = TradeExecutor(
        exchange=FakeExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=FakePositionManager(),
    )

    with pytest.raises(RuntimeError, match="POSITION_ACTIVE_UNPROTECTED"):
        executor.execute_trade(
            "BTCUSDT",
            {
                "status": "GUARDIAN_APPROVED",
            },
        )


def test_recover_protection_succeeds_after_reapplication():
    from execution.trade_executor import TradeExecutor

    events = []

    class FakeExchange:
        def set_trading_stop(self, **kwargs):
            events.append("protection")
            return {
                "retCode": 0,
                "result": {},
            }

    class FakeOrderEngine:
        def prepare_protection_orders(self, symbol, trade_plan):
            events.append("prepare_protection")
            return {
                "category": "linear",
                "symbol": symbol.upper(),
                "tpslMode": "Full",
                "positionIdx": 0,
                "stopLoss": "49000",
                "takeProfit": "52000",
                "slTriggerBy": "MarkPrice",
                "tpTriggerBy": "MarkPrice",
            }

    class FakePositionManager:
        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            events.append("position_verification")
            return {
                "symbol": symbol.upper(),
                "status": "MATCH",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": expected_side,
                "actual_size": expected_size,
                "actual_entry_price": 50000.0,
                "actual_unrealized_pnl": 0.0,
            }

        def get_protection_state(self, symbol):
            events.append("protection_state")
            return {
                "symbol": symbol.upper(),
                "has_position": True,
                "has_stop_loss": True,
                "has_take_profit": True,
                "stop_loss": 49000.0,
                "take_profit": 52000.0,
            }

    executor = TradeExecutor(
        exchange=FakeExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=FakePositionManager(),
    )

    result = executor.recover_protection(
        "BTCUSDT",
        {
            "status": "GUARDIAN_APPROVED",
        },
        {
            "side": "Buy",
            "qty": "0.001",
            "price": "50000",
        },
    )

    assert result["status"] == "PROTECTED"
    assert result["protection_verification"]["safe"] is True
    assert events == [
        "position_verification",
        "prepare_protection",
        "protection",
        "protection_state",
    ]


def test_recover_protection_blocks_when_position_verification_fails():
    from execution.trade_executor import TradeExecutor

    events = []

    class FakeExchange:
        def set_trading_stop(self, **kwargs):
            events.append("protection")
            return {
                "retCode": 0,
                "result": {},
            }

    class FakeOrderEngine:
        def prepare_protection_orders(self, symbol, trade_plan):
            events.append("prepare_protection")
            return {
                "category": "linear",
                "symbol": symbol.upper(),
                "tpslMode": "Full",
                "positionIdx": 0,
                "stopLoss": "49000",
                "takeProfit": "52000",
                "slTriggerBy": "MarkPrice",
                "tpTriggerBy": "MarkPrice",
            }

    class FakePositionManager:
        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            events.append("position_verification")
            return {
                "symbol": symbol.upper(),
                "status": "POSITION_MISMATCH",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": "Sell",
                "actual_size": expected_size,
                "actual_entry_price": 50000.0,
                "actual_unrealized_pnl": 0.0,
            }

    executor = TradeExecutor(
        exchange=FakeExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=FakePositionManager(),
    )

    result = executor.recover_protection(
        "BTCUSDT",
        {
            "status": "GUARDIAN_APPROVED",
        },
        {
            "side": "Buy",
            "qty": "0.001",
            "price": "50000",
        },
    )

    assert result["status"] == "RECOVERY_FAILED"
    assert "POSITION_MISMATCH" in result["reason"]
    assert events == [
        "position_verification",
    ]


def test_recover_protection_handles_reapplication_failure():
    from execution.trade_executor import TradeExecutor

    events = []

    class FakeExchange:
        def set_trading_stop(self, **kwargs):
            events.append("protection")
            raise RuntimeError("Bybit protection request failed")

    class FakeOrderEngine:
        def prepare_protection_orders(self, symbol, trade_plan):
            events.append("prepare_protection")
            return {
                "category": "linear",
                "symbol": symbol.upper(),
                "tpslMode": "Full",
                "positionIdx": 0,
                "stopLoss": "49000",
                "takeProfit": "52000",
                "slTriggerBy": "MarkPrice",
                "tpTriggerBy": "MarkPrice",
            }

    class FakePositionManager:
        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            events.append("position_verification")
            return {
                "symbol": symbol.upper(),
                "status": "MATCH",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": expected_side,
                "actual_size": expected_size,
                "actual_entry_price": 50000.0,
                "actual_unrealized_pnl": 0.0,
            }

    executor = TradeExecutor(
        exchange=FakeExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=FakePositionManager(),
    )

    result = executor.recover_protection(
        "BTCUSDT",
        {
            "status": "GUARDIAN_APPROVED",
        },
        {
            "side": "Buy",
            "qty": "0.001",
            "price": "50000",
        },
    )

    assert result["status"] == "RECOVERY_FAILED"
    assert "Protection reapplication failed" in result["reason"]
    assert events == [
        "position_verification",
        "prepare_protection",
        "protection",
    ]


def test_recover_protection_fails_when_protection_remains_mismatched():
    from execution.trade_executor import TradeExecutor

    events = []

    class FakeExchange:
        def set_trading_stop(self, **kwargs):
            events.append("protection")
            return {
                "retCode": 0,
                "result": {},
            }

    class FakeOrderEngine:
        def prepare_protection_orders(self, symbol, trade_plan):
            events.append("prepare_protection")
            return {
                "category": "linear",
                "symbol": symbol.upper(),
                "tpslMode": "Full",
                "positionIdx": 0,
                "stopLoss": "49000",
                "takeProfit": "52000",
                "slTriggerBy": "MarkPrice",
                "tpTriggerBy": "MarkPrice",
            }

    class FakePositionManager:
        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            events.append("position_verification")
            return {
                "symbol": symbol.upper(),
                "status": "MATCH",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": expected_side,
                "actual_size": expected_size,
                "actual_entry_price": 50000.0,
                "actual_unrealized_pnl": 0.0,
            }

        def get_protection_state(self, symbol):
            events.append("protection_state")
            return {
                "symbol": symbol.upper(),
                "has_position": True,
                "has_stop_loss": True,
                "has_take_profit": True,
                "stop_loss": 48900.0,
                "take_profit": 52000.0,
            }

    executor = TradeExecutor(
        exchange=FakeExchange(),
        order_engine=FakeOrderEngine(),
        position_manager=FakePositionManager(),
    )

    result = executor.recover_protection(
        "BTCUSDT",
        {
            "status": "GUARDIAN_APPROVED",
        },
        {
            "side": "Buy",
            "qty": "0.001",
            "price": "50000",
        },
    )

    assert result["status"] == "RECOVERY_FAILED"
    assert "PROTECTION_MISMATCH" in result["reason"]
    assert result["protection_verification"]["safe"] is False

    assert events == [
        "position_verification",
        "prepare_protection",
        "protection",
        "protection_state",
    ]


def test_execute_trade_rechecks_protection_after_application_exception():
    class AmbiguousProtectionExchange:
        def __init__(self):
            self.protection_calls = 0

        def get_open_orders(self, symbol=None):
            return []

        def create_order(self, **kwargs):
            return {
                "orderId": "TEST-AMBIGUOUS-PROTECTION",
                "orderStatus": "Filled",
            }

        def get_order(self, symbol, order_id):
            return {
                "orderId": order_id,
                "orderStatus": "Filled",
            }

        def get_position(self, symbol):
            return {
                "symbol": symbol.upper(),
                "side": "Buy",
                "size": "0.003",
                "avgPrice": "86854.10",
                "unrealisedPnl": "0",
                "stopLoss": "86001.20",
                "takeProfit": "88555.60",
            }

        def set_trading_stop(self, **kwargs):
            self.protection_calls += 1
            raise RuntimeError(
                "Protection request response was lost."
            )

    class AmbiguousProtectionOrderEngine(FakeOrderEngine):
        def prepare_protection_orders(self, symbol, trade_plan):
            return {
                "category": "linear",
                "symbol": symbol.upper(),
                "tpslMode": "Full",
                "positionIdx": 0,
                "stopLoss": "86001.20",
                "takeProfit": "88555.60",
                "slTriggerBy": "MarkPrice",
                "tpTriggerBy": "MarkPrice",
            }

    class AmbiguousProtectionPositionManager(FakePositionManager):
        def reconcile_position(
            self,
            symbol,
            expected_side=None,
            expected_size=0.0,
        ):
            return {
                "symbol": symbol.upper(),
                "status": "MATCH",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": "Buy",
                "actual_size": 0.003,
                "actual_entry_price": 86854.10,
                "actual_unrealized_pnl": 0.0,
            }

        def get_position(self, symbol):
            return exchange.get_position(symbol)

        def get_protection_state(self, symbol):
            position = self.get_position(symbol)

            return {
                "symbol": symbol.upper(),
                "has_position": True,
                "has_stop_loss": position["stopLoss"] is not None,
                "has_take_profit": position["takeProfit"] is not None,
                "stop_loss": float(position["stopLoss"]),
                "take_profit": float(position["takeProfit"]),
            }

    exchange = AmbiguousProtectionExchange()

    executor = TradeExecutor(
        exchange=exchange,
        order_engine=AmbiguousProtectionOrderEngine(),
        position_manager=AmbiguousProtectionPositionManager(False),
    )

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
        "direction": "long",
        "position_size": "0.003",
        "entry_price": "86854.137",
        "stop_loss": "86001.234",
        "take_profit": "88555.678",
    }

    result = executor.execute_trade(
        "btcusdt",
        trade_plan,
    )

    assert result["status"] == "PROTECTED"
    assert result["protection_verification"]["status"] == "MATCH"
    assert exchange.protection_calls == 1
