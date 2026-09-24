class PositionSafetyMonitor:
    """
    Validates that the actual exchange position matches the expected state.

    This layer observes and reports position anomalies.
    It does not place, modify, or close orders.
    """

    SAFE_STATUSES = {"MATCH"}

    def __init__(self, position_manager):
        self.position_manager = position_manager

    def check(
        self,
        symbol: str,
        expected_side: str | None = None,
        expected_size: float = 0.0,
    ) -> dict:
        if not symbol:
            raise ValueError("Symbol is required.")

        result = self.position_manager.reconcile_position(
            symbol.upper(),
            expected_side=expected_side,
            expected_size=expected_size,
        )

        result["safe"] = result["status"] in self.SAFE_STATUSES

        return result


    def enforce_kill_switch(self, kill_switch, result: dict) -> None:
        """
        Activate the kill switch when a position state is unsafe.
        """
        if not isinstance(result, dict):
            raise ValueError("Position safety result must be a dictionary.")

        if not result.get("safe", False):
            status = result.get("status", "UNKNOWN")
            kill_switch.activate(
                f"Position safety failure: {status}"
            )
