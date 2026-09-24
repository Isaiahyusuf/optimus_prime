class ProtectionRecovery:
    """
    Determines the recovery action required when exchange-reported
    TP/SL protection does not match the intended protection.

    This layer is initially read-only.
    It does not modify exchange state or perform automatic retries.
    """

    SAFE_STATUS = "MATCH"

    def __init__(self, position_manager):
        if position_manager is None:
            raise ValueError("Position manager is required.")

        self.position_manager = position_manager

    def evaluate(
        self,
        symbol: str,
        expected_stop_loss: float,
        expected_take_profit: float,
    ) -> dict:
        """
        Evaluate the current protection state and determine
        whether recovery is required.
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
                "status": "NO_POSITION",
                "safe": False,
                "recovery_required": False,
                "action": "NO_ACTION",
                "reason": "No active position exists.",
            }

        if (
            not actual.get("has_stop_loss", False)
            or not actual.get("has_take_profit", False)
        ):
            return {
                "symbol": symbol,
                "status": "MISSING_PROTECTION",
                "safe": False,
                "recovery_required": True,
                "action": "REAPPLY_PROTECTION",
                "reason": "Active position is missing TP/SL protection.",
            }

        actual_stop_loss = actual.get("stop_loss")
        actual_take_profit = actual.get("take_profit")

        if actual_stop_loss is None or actual_take_profit is None:
            return {
                "symbol": symbol,
                "status": "MISSING_PROTECTION",
                "safe": False,
                "recovery_required": True,
                "action": "REAPPLY_PROTECTION",
                "reason": "Active position has incomplete TP/SL protection.",
            }

        if (
            actual_stop_loss != expected_stop_loss
            or actual_take_profit != expected_take_profit
        ):
            return {
                "symbol": symbol,
                "status": "PROTECTION_MISMATCH",
                "safe": False,
                "recovery_required": True,
                "action": "REAPPLY_PROTECTION",
                "reason": "Exchange TP/SL does not match intended protection.",
            }

        return {
            "symbol": symbol,
            "status": self.SAFE_STATUS,
            "safe": True,
            "recovery_required": False,
            "action": "NO_ACTION",
            "reason": "Exchange protection matches intended TP/SL.",
        }
