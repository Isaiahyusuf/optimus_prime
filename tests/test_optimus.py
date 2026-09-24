import pytest

from core.optimus import OptimusPrime


class FakeExchange:
    def __init__(self, response):
        self.response = response

    def get_wallet_balance(self, coin):
        return self.response

    def get_server_time(self):
        return {"timeSecond": "0"}


class FakeGuardian:
    def __init__(self):
        self.calls = []

    def generate(self, setup, liquidity_levels, account_equity):
        self.calls.append(
            {
                "setup": setup,
                "liquidity_levels": liquidity_levels,
                "account_equity": account_equity,
            }
        )

        return {
            "approved": True,
            "status": "GUARDIAN_APPROVED",
            "reason": "test_approval",
        }


def test_optimus_accepts_injected_exchange():
    exchange = FakeExchange({"totalEquity": "2500.75"})

    optimus = OptimusPrime(exchange=exchange)

    assert optimus.exchange is exchange
    assert optimus.status == "INITIALIZING"


def test_optimus_get_account_equity():
    exchange = FakeExchange({"totalEquity": "2500.75"})

    optimus = OptimusPrime(exchange=exchange)

    assert optimus.get_account_equity() == 2500.75


def test_optimus_rejects_invalid_equity():
    exchange = FakeExchange({"totalEquity": "0"})

    optimus = OptimusPrime(exchange=exchange)

    with pytest.raises(ValueError, match="greater than zero"):
        optimus.get_account_equity()


def test_optimus_start_and_shutdown():
    exchange = FakeExchange({"totalEquity": "2500.75"})

    optimus = OptimusPrime(exchange=exchange)

    optimus.start()
    assert optimus.status == "ONLINE"

    optimus.shutdown()
    assert optimus.status == "OFFLINE"


def test_optimus_generates_guardian_trade_plans():
    exchange = FakeExchange({"totalEquity": "2500.75"})
    guardian = FakeGuardian()

    optimus = OptimusPrime(
        exchange=exchange,
        guardian=guardian,
    )

    scan_results = [
        {
            "symbol": "BTCUSDT",
            "analysis": {
                "liquidity": [
                    {
                        "type": "buy_side",
                        "price": 90000,
                    }
                ]
            },
            "valid_setups": [
                {
                    "setup_status": "valid_setup",
                    "setup_score": 90,
                }
            ],
        }
    ]

    plans = optimus.generate_trade_plans(scan_results)

    assert len(plans) == 1
    assert plans[0]["symbol"] == "BTCUSDT"
    assert plans[0]["plan"]["status"] == "GUARDIAN_APPROVED"

    assert len(guardian.calls) == 1
    assert guardian.calls[0]["account_equity"] == 2500.75
    assert guardian.calls[0]["setup"]["setup_status"] == "valid_setup"


def test_optimus_ignores_scan_results_without_valid_setups():
    exchange = FakeExchange({"totalEquity": "2500.75"})
    guardian = FakeGuardian()

    optimus = OptimusPrime(
        exchange=exchange,
        guardian=guardian,
    )

    scan_results = [
        {
            "symbol": "BTCUSDT",
            "analysis": {
                "liquidity": [],
            },
            "valid_setups": [],
        }
    ]

    plans = optimus.generate_trade_plans(scan_results)

    assert plans == []
    assert guardian.calls == []


def test_optimus_rejects_invalid_scan_results():
    exchange = FakeExchange({"totalEquity": "2500.75"})
    guardian = FakeGuardian()

    optimus = OptimusPrime(
        exchange=exchange,
        guardian=guardian,
    )

    with pytest.raises(ValueError, match="Scan results must be a list"):
        optimus.generate_trade_plans({})


def test_optimus_scans_market_and_generates_trade_plans():
    class FakeScanner:
        def __init__(self):
            self.scan_called = False

        def scan(self):
            self.scan_called = True
            return [
                {
                    "symbol": "BTCUSDT",
                    "analysis": {
                        "liquidity": [
                            {
                                "type": "buy_side",
                                "price": 90000,
                            }
                        ]
                    },
                    "valid_setups": [
                        {
                            "setup_status": "valid_setup",
                            "setup_score": 95,
                        }
                    ],
                }
            ]

    exchange = FakeExchange({"totalEquity": "2500.75"})
    guardian = FakeGuardian()
    scanner = FakeScanner()

    optimus = OptimusPrime(
        exchange=exchange,
        guardian=guardian,
        scanner=scanner,
    )

    plans = optimus.scan_and_generate_trade_plans()

    assert scanner.scan_called is True
    assert len(plans) == 1
    assert plans[0]["symbol"] == "BTCUSDT"
    assert plans[0]["plan"]["status"] == "GUARDIAN_APPROVED"

    assert len(guardian.calls) == 1
    assert guardian.calls[0]["account_equity"] == 2500.75


def test_optimus_system_health_keeps_kill_switch_clear_when_exchange_is_healthy():
    class HealthyExchange(FakeExchange):
        def get_server_time(self):
            return {"timeSecond": "1234567890"}

    exchange = HealthyExchange({"totalEquity": "2500.75"})
    optimus = OptimusPrime(exchange=exchange)

    assert optimus.check_system_health() is True
    assert optimus.health_monitor.is_healthy() is True
    assert optimus.kill_switch.is_active() is False


def test_optimus_system_health_activates_kill_switch_when_exchange_fails():
    class FailingExchange(FakeExchange):
        def get_server_time(self):
            raise RuntimeError("test exchange unavailable")

    exchange = FailingExchange({"totalEquity": "2500.75"})
    optimus = OptimusPrime(exchange=exchange)

    assert optimus.check_system_health() is False
    assert optimus.health_monitor.is_healthy() is False
    assert optimus.kill_switch.is_active() is True
    assert "test exchange unavailable" in optimus.kill_switch.reason()


def test_optimus_wires_trade_executor_dependencies():
    exchange = FakeExchange({"totalEquity": "2500.75"})

    optimus = OptimusPrime(exchange=exchange)

    assert optimus.order_engine.exchange is exchange
    assert optimus.position_manager.exchange is exchange
    assert optimus.trade_executor.exchange is exchange
    assert optimus.trade_executor.order_engine is optimus.order_engine
    assert optimus.trade_executor.position_manager is optimus.position_manager
    assert optimus.trade_executor.kill_switch is optimus.kill_switch


def test_optimus_executes_guardian_trade_plan_through_trade_executor():
    class FakeTradeExecutor:
        def __init__(self):
            self.calls = []

        def execute_trade(self, symbol, trade_plan):
            self.calls.append((symbol, trade_plan))
            return {
                "symbol": symbol.upper(),
                "entry": {"orderId": "TEST-001"},
                "verification": {"status": "MATCH"},
                "protection": {"retCode": 0},
            }

    exchange = FakeExchange({"totalEquity": "2500.75"})
    optimus = OptimusPrime(exchange=exchange)

    fake_executor = FakeTradeExecutor()
    optimus.trade_executor = fake_executor

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
        "direction": "long",
        "position_size": "0.003",
        "entry_price": "86854.137",
        "stop_loss": "86001.234",
        "take_profit": "88555.678",
    }

    result = optimus.execute_trade_plan(
        "btcusdt",
        trade_plan,
    )

    assert result["symbol"] == "BTCUSDT"
    assert result["verification"]["status"] == "MATCH"
    assert fake_executor.calls == [
        ("btcusdt", trade_plan),
    ]
