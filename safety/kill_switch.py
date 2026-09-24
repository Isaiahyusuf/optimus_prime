class KillSwitch:
    """
    Execution safety kill switch.

    When active, new trade execution must be blocked.
    """

    def __init__(self):
        self._active = False
        self._reason = None

    def activate(self, reason: str) -> None:
        if not reason or not reason.strip():
            raise ValueError("Kill switch activation requires a reason.")

        self._active = True
        self._reason = reason.strip()

    def deactivate(self) -> None:
        self._active = False
        self._reason = None

    def is_active(self) -> bool:
        return self._active

    def reason(self) -> str | None:
        return self._reason

    def check(self) -> None:
        if self._active:
            raise RuntimeError(
                "KILL_SWITCH_ACTIVE: "
                f"{self._reason}"
            )
