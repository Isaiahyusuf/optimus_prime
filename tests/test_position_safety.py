from safety.position_safety import PositionSafetyMonitor


def test_matching_position_is_safe():
    class FakePositionManager:
        def reconcile_position(self, symbol, expected_side=None, expected_size=0.0):
            return {
                "symbol": symbol,
                "status": "MATCH",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": expected_side,
                "actual_size": expected_size,
                "actual_entry_price": 100.0,
                "actual_unrealized_pnl": 0.0,
            }

    monitor = PositionSafetyMonitor(FakePositionManager())

    result = monitor.check("BTCUSDT", expected_side="Buy", expected_size=0.01)

    assert result["status"] == "MATCH"
    assert result["safe"] is True


def test_missing_position_is_unsafe():
    class FakePositionManager:
        def reconcile_position(self, symbol, expected_side=None, expected_size=0.0):
            return {
                "symbol": symbol,
                "status": "MISSING_POSITION",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": None,
                "actual_size": 0.0,
                "actual_entry_price": 0.0,
                "actual_unrealized_pnl": 0.0,
            }

    monitor = PositionSafetyMonitor(FakePositionManager())

    result = monitor.check("BTCUSDT", expected_side="Buy", expected_size=0.01)

    assert result["status"] == "MISSING_POSITION"
    assert result["safe"] is False


def test_unexpected_position_is_unsafe():
    class FakePositionManager:
        def reconcile_position(self, symbol, expected_side=None, expected_size=0.0):
            return {
                "symbol": symbol,
                "status": "UNEXPECTED_POSITION",
                "expected_side": None,
                "expected_size": 0.0,
                "actual_side": "Buy",
                "actual_size": 0.01,
                "actual_entry_price": 100.0,
                "actual_unrealized_pnl": 0.0,
            }

    monitor = PositionSafetyMonitor(FakePositionManager())

    result = monitor.check("BTCUSDT")

    assert result["status"] == "UNEXPECTED_POSITION"
    assert result["safe"] is False


def test_position_side_mismatch_is_unsafe():
    class FakePositionManager:
        def reconcile_position(self, symbol, expected_side=None, expected_size=0.0):
            return {
                "symbol": symbol,
                "status": "POSITION_MISMATCH",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": "Sell",
                "actual_size": expected_size,
                "actual_entry_price": 100.0,
                "actual_unrealized_pnl": 0.0,
            }

    monitor = PositionSafetyMonitor(FakePositionManager())

    result = monitor.check("BTCUSDT", expected_side="Buy", expected_size=0.01)

    assert result["status"] == "POSITION_MISMATCH"
    assert result["safe"] is False


def test_position_size_mismatch_is_unsafe():
    class FakePositionManager:
        def reconcile_position(self, symbol, expected_side=None, expected_size=0.0):
            return {
                "symbol": symbol,
                "status": "SIZE_MISMATCH",
                "expected_side": expected_side,
                "expected_size": expected_size,
                "actual_side": expected_side,
                "actual_size": 0.02,
                "actual_entry_price": 100.0,
                "actual_unrealized_pnl": 0.0,
            }

    monitor = PositionSafetyMonitor(FakePositionManager())

    result = monitor.check("BTCUSDT", expected_side="Buy", expected_size=0.01)

    assert result["status"] == "SIZE_MISMATCH"
    assert result["safe"] is False


class MockPositionManager:
    def __init__(self, result):
        self.result = result

    def reconcile_position(self, symbol, expected_side=None, expected_size=0.0):
        return self.result.copy()

def test_safe_position_does_not_activate_kill_switch():
    from safety.kill_switch import KillSwitch

    position_manager = MockPositionManager(
        {
            "status": "MATCH",
            "actual_side": "Buy",
            "actual_size": 1.0,
        }
    )
    monitor = PositionSafetyMonitor(position_manager)
    kill_switch = KillSwitch()

    result = monitor.check("BTCUSDT", expected_side="Buy", expected_size=1.0)
    monitor.enforce_kill_switch(kill_switch, result)

    assert kill_switch.is_active() is False


def test_unsafe_position_activates_kill_switch():
    from safety.kill_switch import KillSwitch

    position_manager = MockPositionManager(
        {
            "status": "SIZE_MISMATCH",
            "actual_side": "Buy",
            "actual_size": 0.5,
        }
    )
    monitor = PositionSafetyMonitor(position_manager)
    kill_switch = KillSwitch()

    result = monitor.check("BTCUSDT", expected_side="Buy", expected_size=1.0)
    monitor.enforce_kill_switch(kill_switch, result)

    assert kill_switch.is_active() is True
    assert kill_switch.reason() == "Position safety failure: SIZE_MISMATCH"
