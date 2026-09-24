from execution.position_manager import PositionManager


class FakeExchange:
    def __init__(self, position=None):
        self.position = position
        self.requested_symbol = None

    def get_position(self, symbol):
        self.requested_symbol = symbol
        return self.position


def test_get_position_returns_active_position():
    position = {
        "symbol": "BTCUSDT",
        "size": "0.003",
        "side": "Buy",
    }

    exchange = FakeExchange(position)
    manager = PositionManager(exchange)

    result = manager.get_position("btcusdt")

    assert result == position
    assert exchange.requested_symbol == "BTCUSDT"


def test_get_position_returns_none_when_no_position():
    exchange = FakeExchange(None)
    manager = PositionManager(exchange)

    assert manager.get_position("BTCUSDT") is None


def test_has_position_returns_true_when_active():
    exchange = FakeExchange({
        "symbol": "BTCUSDT",
        "size": "0.003",
    })

    manager = PositionManager(exchange)

    assert manager.has_position("BTCUSDT") is True


def test_has_position_returns_false_when_no_position():
    exchange = FakeExchange(None)
    manager = PositionManager(exchange)

    assert manager.has_position("BTCUSDT") is False


def test_get_position_requires_symbol():
    exchange = FakeExchange()
    manager = PositionManager(exchange)

    try:
        manager.get_position("")
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert str(exc) == "Symbol is required."


def test_get_position_state_normalizes_active_position():
    position = {
        "symbol": "BTCUSDT",
        "size": "0.003",
        "side": "Buy",
        "avgPrice": "100000.50",
        "unrealisedPnl": "12.75",
    }

    exchange = FakeExchange(position)
    manager = PositionManager(exchange)

    result = manager.get_position_state("btcusdt")

    assert result == {
        "symbol": "BTCUSDT",
        "has_position": True,
        "side": "Buy",
        "size": 0.003,
        "entry_price": 100000.50,
        "unrealized_pnl": 12.75,
    }


def test_get_position_state_returns_empty_state_without_position():
    exchange = FakeExchange(None)
    manager = PositionManager(exchange)

    result = manager.get_position_state("BTCUSDT")

    assert result == {
        "symbol": "BTCUSDT",
        "has_position": False,
        "side": None,
        "size": 0.0,
        "entry_price": 0.0,
        "unrealized_pnl": 0.0,
    }


def test_get_position_state_handles_malformed_numeric_values():
    position = {
        "symbol": "BTCUSDT",
        "size": "invalid",
        "side": "Buy",
        "avgPrice": "invalid",
        "unrealisedPnl": "invalid",
    }

    exchange = FakeExchange(position)
    manager = PositionManager(exchange)

    result = manager.get_position_state("BTCUSDT")

    assert result == {
        "symbol": "BTCUSDT",
        "has_position": False,
        "side": "Buy",
        "size": 0.0,
        "entry_price": 0.0,
        "unrealized_pnl": 0.0,
    }


def test_reconcile_position_matches_when_both_have_no_position():
    exchange = FakeExchange(None)
    manager = PositionManager(exchange)

    result = manager.reconcile_position("BTCUSDT")

    assert result["status"] == "MATCH"
    assert result["actual_size"] == 0.0


def test_reconcile_position_detects_unexpected_position():
    exchange = FakeExchange({
        "symbol": "BTCUSDT",
        "size": "0.003",
        "side": "Buy",
    })

    manager = PositionManager(exchange)

    result = manager.reconcile_position("BTCUSDT")

    assert result["status"] == "UNEXPECTED_POSITION"


def test_reconcile_position_detects_missing_position():
    exchange = FakeExchange(None)
    manager = PositionManager(exchange)

    result = manager.reconcile_position(
        "BTCUSDT",
        expected_side="Buy",
        expected_size=0.003,
    )

    assert result["status"] == "MISSING_POSITION"


def test_reconcile_position_detects_side_mismatch():
    exchange = FakeExchange({
        "symbol": "BTCUSDT",
        "size": "0.003",
        "side": "Sell",
    })

    manager = PositionManager(exchange)

    result = manager.reconcile_position(
        "BTCUSDT",
        expected_side="Buy",
        expected_size=0.003,
    )

    assert result["status"] == "POSITION_MISMATCH"


def test_reconcile_position_detects_size_mismatch():
    exchange = FakeExchange({
        "symbol": "BTCUSDT",
        "size": "0.005",
        "side": "Buy",
    })

    manager = PositionManager(exchange)

    result = manager.reconcile_position(
        "BTCUSDT",
        expected_side="Buy",
        expected_size=0.003,
    )

    assert result["status"] == "SIZE_MISMATCH"


def test_reconcile_position_matches_expected_position():
    exchange = FakeExchange({
        "symbol": "BTCUSDT",
        "size": "0.003",
        "side": "Buy",
    })

    manager = PositionManager(exchange)

    result = manager.reconcile_position(
        "BTCUSDT",
        expected_side="Buy",
        expected_size=0.003,
    )

    assert result["status"] == "MATCH"


def test_reconcile_position_rejects_invalid_side():
    exchange = FakeExchange(None)
    manager = PositionManager(exchange)

    try:
        manager.reconcile_position(
            "BTCUSDT",
            expected_side="Long",
            expected_size=0.003,
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert str(exc) == "Expected side must be Buy, Sell, or None."


def test_reconcile_position_rejects_negative_size():
    exchange = FakeExchange(None)
    manager = PositionManager(exchange)

    try:
        manager.reconcile_position(
            "BTCUSDT",
            expected_size=-0.001,
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert str(exc) == "Expected size cannot be negative."


def test_get_protection_state_returns_unprotected_when_no_position():
    exchange = FakeExchange(None)
    manager = PositionManager(exchange)

    result = manager.get_protection_state("BTCUSDT")

    assert result == {
        "symbol": "BTCUSDT",
        "has_position": False,
        "has_stop_loss": False,
        "has_take_profit": False,
        "stop_loss": None,
        "take_profit": None,
    }


def test_get_protection_state_detects_tp_and_sl():
    exchange = FakeExchange({
        "symbol": "BTCUSDT",
        "size": "0.003",
        "side": "Buy",
        "stopLoss": "99000",
        "takeProfit": "105000",
    })

    manager = PositionManager(exchange)

    result = manager.get_protection_state("BTCUSDT")

    assert result == {
        "symbol": "BTCUSDT",
        "has_position": True,
        "has_stop_loss": True,
        "has_take_profit": True,
        "stop_loss": 99000.0,
        "take_profit": 105000.0,
    }


def test_get_protection_state_detects_missing_take_profit():
    exchange = FakeExchange({
        "symbol": "BTCUSDT",
        "size": "0.003",
        "side": "Buy",
        "stopLoss": "99000",
        "takeProfit": "",
    })

    manager = PositionManager(exchange)

    result = manager.get_protection_state("BTCUSDT")

    assert result["has_position"] is True
    assert result["has_stop_loss"] is True
    assert result["has_take_profit"] is False
    assert result["stop_loss"] == 99000.0
    assert result["take_profit"] is None


def test_get_protection_state_rejects_malformed_stop_loss():
    exchange = FakeExchange({
        "symbol": "BTCUSDT",
        "size": "0.003",
        "side": "Buy",
        "stopLoss": "invalid",
        "takeProfit": "105000",
    })

    manager = PositionManager(exchange)

    try:
        manager.get_protection_state("BTCUSDT")
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert str(exc) == "Stop loss must be numeric when provided."
