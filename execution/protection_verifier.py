class ProtectionVerifier:
    """
    Verifies that exchange-reported TP/SL protection matches
    the protection Optimus Prime intended.

    This layer is read-only. It never applies, modifies, or
    removes protection.
    """

    SAFE_STATUSES = {"MATCH"}

    def __init__(self, position_manager, tolerance: float = 1e-6):
        if position_manager is None:
            raise ValueError("Position manager is required.")

        if tolerance < 0:
            raise ValueError("Tolerance cannot be negative.")

        self.position_manager = position_manager
        self.tolerance = tolerance

    def verify(
        self,
        symbol: str,
        expected_stop_loss: float,
        expected_take_profit: float,
    ) -> dict:
        """
        Compare expected TP/SL with exchange-reported protection.
        """

        if not symbol:
            raise ValueError("Symbol is required.")

        if expected_stop_loss <= 0:
            raise ValueError(
                "Expected stop loss must be greater than zero."
            )

        if expected_take_profit <= 0:
            raise ValueError(
                "Expected take profit must be greater than zero."
            )

        symbol = symbol.upper()

        actual = self.position_manager.get_protection_state(symbol)

        if not actual.get("has_position", False):
            return {
                "symbol": symbol,
                "status": "MISSING_PROTECTION",
                "safe": False,
                "expected_stop_loss": expected_stop_loss,
                "expected_take_profit": expected_take_profit,
                "actual_stop_loss": None,
                "actual_take_profit": None,
            }

        actual_stop_loss = actual.get("stop_loss")
        actual_take_profit = actual.get("take_profit")

        if (
            not actual.get("has_stop_loss", False)
            or not actual.get("has_take_profit", False)
            or actual_stop_loss is None
            or actual_take_profit is None
        ):
            return {
                "symbol": symbol,
                "status": "MISSING_PROTECTION",
                "safe": False,
                "expected_stop_loss": expected_stop_loss,
                "expected_take_profit": expected_take_profit,
                "actual_stop_loss": actual_stop_loss,
                "actual_take_profit": actual_take_profit,
            }

        stop_loss_matches = (
            abs(actual_stop_loss - expected_stop_loss)
            <= self.tolerance
        )

        take_profit_matches = (
            abs(actual_take_profit - expected_take_profit)
            <= self.tolerance
        )

        if not stop_loss_matches or not take_profit_matches:
            return {
                "symbol": symbol,
                "status": "PROTECTION_MISMATCH",
                "safe": False,
                "expected_stop_loss": expected_stop_loss,
                "expected_take_profit": expected_take_profit,
                "actual_stop_loss": actual_stop_loss,
                "actual_take_profit": actual_take_profit,
            }

        return {
            "symbol": symbol,
            "status": "MATCH",
            "safe": True,
            "expected_stop_loss": expected_stop_loss,
            "expected_take_profit": expected_take_profit,
            "actual_stop_loss": actual_stop_loss,
            "actual_take_profit": actual_take_profit,
        }
