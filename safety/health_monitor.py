class HealthMonitor:
    """
    Execution health monitor.

    This layer observes execution safety state.
    It does not place, modify, or close orders.
    """

    def __init__(self):
        self._healthy = True
        self._reason = None

    def mark_unhealthy(self, reason: str) -> None:
        if not reason or not reason.strip():
            raise ValueError("Health failure requires a reason.")

        self._healthy = False
        self._reason = reason.strip()

    def mark_healthy(self) -> None:
        self._healthy = True
        self._reason = None

    def is_healthy(self) -> bool:
        return self._healthy

    def reason(self) -> str | None:
        return self._reason

    def check(self) -> None:
        if not self._healthy:
            raise RuntimeError(
                "EXECUTION_UNHEALTHY: "
                f"{self._reason}"
            )


    def check_exchange_connectivity(self, exchange) -> bool:
        """
        Verify that the exchange can be reached.

        Uses a read-only exchange endpoint.
        Does not place, modify, or close orders.
        """
        try:
            exchange.get_server_time()
        except Exception as exc:
            self.mark_unhealthy(
                f"Exchange connectivity check failed: {exc}"
            )
            return False

        self.mark_healthy()
        return True


    def enforce_kill_switch(self, kill_switch) -> None:
        """
        Activate the kill switch when execution health is unhealthy.
        """
        if not self.is_healthy():
            kill_switch.activate(
                self.reason() or "Execution health check failed."
            )
