from execution.protection_verifier import ProtectionVerifier


def test_matching_protection_is_verified():
    class FakePositionManager:
        def get_protection_state(self, symbol):
            return {
                "symbol": symbol,
                "has_position": True,
                "has_stop_loss": True,
                "has_take_profit": True,
                "stop_loss": 95.0,
                "take_profit": 110.0,
            }

    verifier = ProtectionVerifier(FakePositionManager())

    result = verifier.verify(
        "BTCUSDT",
        expected_stop_loss=95.0,
        expected_take_profit=110.0,
    )

    assert result["status"] == "MATCH"
    assert result["safe"] is True


def test_missing_protection_is_unsafe():
    class FakePositionManager:
        def get_protection_state(self, symbol):
            return {
                "symbol": symbol,
                "has_position": True,
                "has_stop_loss": False,
                "has_take_profit": True,
                "stop_loss": None,
                "take_profit": 110.0,
            }

    verifier = ProtectionVerifier(FakePositionManager())

    result = verifier.verify(
        "BTCUSDT",
        expected_stop_loss=95.0,
        expected_take_profit=110.0,
    )

    assert result["status"] == "MISSING_PROTECTION"
    assert result["safe"] is False


def test_mismatched_protection_is_unsafe():
    class FakePositionManager:
        def get_protection_state(self, symbol):
            return {
                "symbol": symbol,
                "has_position": True,
                "has_stop_loss": True,
                "has_take_profit": True,
                "stop_loss": 94.0,
                "take_profit": 110.0,
            }

    verifier = ProtectionVerifier(FakePositionManager())

    result = verifier.verify(
        "BTCUSDT",
        expected_stop_loss=95.0,
        expected_take_profit=110.0,
    )

    assert result["status"] == "PROTECTION_MISMATCH"
    assert result["safe"] is False


def test_small_price_difference_within_tolerance_matches():
    class FakePositionManager:
        def get_protection_state(self, symbol):
            return {
                "symbol": symbol,
                "has_position": True,
                "has_stop_loss": True,
                "has_take_profit": True,
                "stop_loss": 95.00000001,
                "take_profit": 109.99999999,
            }

    verifier = ProtectionVerifier(
        FakePositionManager(),
        tolerance=1e-6,
    )

    result = verifier.verify(
        "BTCUSDT",
        expected_stop_loss=95.0,
        expected_take_profit=110.0,
    )

    assert result["status"] == "MATCH"
    assert result["safe"] is True


def test_invalid_expected_stop_loss_is_rejected():
    class FakePositionManager:
        def get_protection_state(self, symbol):
            raise AssertionError("Exchange state should not be queried.")

    verifier = ProtectionVerifier(FakePositionManager())

    try:
        verifier.verify(
            "BTCUSDT",
            expected_stop_loss=0.0,
            expected_take_profit=110.0,
        )
    except ValueError as exc:
        assert str(exc) == "Expected stop loss must be greater than zero."
    else:
        raise AssertionError("Expected ValueError.")


def test_invalid_expected_take_profit_is_rejected():
    class FakePositionManager:
        def get_protection_state(self, symbol):
            raise AssertionError("Exchange state should not be queried.")

    verifier = ProtectionVerifier(FakePositionManager())

    try:
        verifier.verify(
            "BTCUSDT",
            expected_stop_loss=95.0,
            expected_take_profit=0.0,
        )
    except ValueError as exc:
        assert str(exc) == "Expected take profit must be greater than zero."
    else:
        raise AssertionError("Expected ValueError.")


def test_difference_outside_tolerance_is_mismatch():
    class FakePositionManager:
        def get_protection_state(self, symbol):
            return {
                "symbol": symbol,
                "has_position": True,
                "has_stop_loss": True,
                "has_take_profit": True,
                "stop_loss": 95.01,
                "take_profit": 110.0,
            }

    verifier = ProtectionVerifier(
        FakePositionManager(),
        tolerance=1e-6,
    )

    result = verifier.verify(
        "BTCUSDT",
        expected_stop_loss=95.0,
        expected_take_profit=110.0,
    )

    assert result["status"] == "PROTECTION_MISMATCH"
    assert result["safe"] is False
