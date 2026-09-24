import pytest

from execution.protection_recovery import ProtectionRecovery


class FakePositionManager:
    def __init__(self, protection_state):
        self.protection_state = protection_state
        self.calls = []

    def get_protection_state(self, symbol):
        self.calls.append(symbol)
        return self.protection_state


def test_matching_protection_requires_no_recovery():
    manager = FakePositionManager(
        {
            "symbol": "BTCUSDT",
            "has_position": True,
            "has_stop_loss": True,
            "has_take_profit": True,
            "stop_loss": 49000.0,
            "take_profit": 52000.0,
        }
    )

    recovery = ProtectionRecovery(manager)

    result = recovery.evaluate(
        "btcusdt",
        expected_stop_loss=49000.0,
        expected_take_profit=52000.0,
    )

    assert result["symbol"] == "BTCUSDT"
    assert result["status"] == "MATCH"
    assert result["safe"] is True
    assert result["recovery_required"] is False
    assert result["action"] == "NO_ACTION"
    assert manager.calls == ["BTCUSDT"]


def test_missing_protection_requires_recovery():
    manager = FakePositionManager(
        {
            "symbol": "BTCUSDT",
            "has_position": True,
            "has_stop_loss": False,
            "has_take_profit": False,
            "stop_loss": None,
            "take_profit": None,
        }
    )

    recovery = ProtectionRecovery(manager)

    result = recovery.evaluate(
        "BTCUSDT",
        expected_stop_loss=49000.0,
        expected_take_profit=52000.0,
    )

    assert result["status"] == "MISSING_PROTECTION"
    assert result["safe"] is False
    assert result["recovery_required"] is True
    assert result["action"] == "REAPPLY_PROTECTION"


def test_protection_mismatch_requires_recovery():
    manager = FakePositionManager(
        {
            "symbol": "BTCUSDT",
            "has_position": True,
            "has_stop_loss": True,
            "has_take_profit": True,
            "stop_loss": 48900.0,
            "take_profit": 52000.0,
        }
    )

    recovery = ProtectionRecovery(manager)

    result = recovery.evaluate(
        "BTCUSDT",
        expected_stop_loss=49000.0,
        expected_take_profit=52000.0,
    )

    assert result["status"] == "PROTECTION_MISMATCH"
    assert result["safe"] is False
    assert result["recovery_required"] is True
    assert result["action"] == "REAPPLY_PROTECTION"


def test_no_position_requires_no_recovery_action():
    manager = FakePositionManager(
        {
            "symbol": "BTCUSDT",
            "has_position": False,
            "has_stop_loss": False,
            "has_take_profit": False,
            "stop_loss": None,
            "take_profit": None,
        }
    )

    recovery = ProtectionRecovery(manager)

    result = recovery.evaluate(
        "BTCUSDT",
        expected_stop_loss=49000.0,
        expected_take_profit=52000.0,
    )

    assert result["status"] == "NO_POSITION"
    assert result["safe"] is False
    assert result["recovery_required"] is False
    assert result["action"] == "NO_ACTION"


def test_invalid_symbol_is_rejected():
    manager = FakePositionManager({})

    recovery = ProtectionRecovery(manager)

    with pytest.raises(ValueError, match="Symbol is required"):
        recovery.evaluate(
            "",
            expected_stop_loss=49000.0,
            expected_take_profit=52000.0,
        )


def test_invalid_stop_loss_is_rejected():
    manager = FakePositionManager({})

    recovery = ProtectionRecovery(manager)

    with pytest.raises(
        ValueError,
        match="Expected stop loss must be greater than zero",
    ):
        recovery.evaluate(
            "BTCUSDT",
            expected_stop_loss=0,
            expected_take_profit=52000.0,
        )


def test_invalid_take_profit_is_rejected():
    manager = FakePositionManager({})

    recovery = ProtectionRecovery(manager)

    with pytest.raises(
        ValueError,
        match="Expected take profit must be greater than zero",
    ):
        recovery.evaluate(
            "BTCUSDT",
            expected_stop_loss=49000.0,
            expected_take_profit=0,
        )
