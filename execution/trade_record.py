class TradeRecord:
    """
    Represents the lifecycle state of one executed trade attempt.

    This layer stores execution state only.
    It does not query or modify exchange state.
    """

    VALID_STATES = {
        "CREATED",
        "ENTRY_SUBMITTED",
        "ENTRY_PENDING",
        "ENTRY_PARTIALLY_FILLED",
        "ENTRY_FILLED",
        "POSITION_VERIFICATION_FAILED",
        "POSITION_VERIFIED",
        "PROTECTION_APPLIED",
        "PROTECTION_FAILED",
        "ENTRY_CANCELLED",
        "ENTRY_CANCELLATION_FAILED",
        "ENTRY_REJECTED",
        "ENTRY_STATE_UNKNOWN",
    }

    def __init__(
        self,
        symbol: str,
        order_id: str | None = None,
        state: str = "CREATED",
    ):
        if not symbol:
            raise ValueError("Symbol is required.")

        if state not in self.VALID_STATES:
            raise ValueError(
                f"Invalid trade record state: {state}"
            )

        self.symbol = symbol.upper()
        self.order_id = order_id
        self.state = state
        self.order_quantity = None
        self.filled_quantity = None
        self.remaining_quantity = None
        self.average_fill_price = None

    def update_state(self, state: str) -> None:
        if state not in self.VALID_STATES:
            raise ValueError(
                f"Invalid trade record state: {state}"
            )

        self.state = state

    def update_execution(
        self,
        order_quantity: float,
        filled_quantity: float,
        remaining_quantity: float,
        average_fill_price: float,
    ) -> None:
        self.order_quantity = order_quantity
        self.filled_quantity = filled_quantity
        self.remaining_quantity = remaining_quantity
        self.average_fill_price = average_fill_price

    def snapshot(self) -> dict:
        return {
            "symbol": self.symbol,
            "order_id": self.order_id,
            "state": self.state,
            "order_quantity": self.order_quantity,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "average_fill_price": self.average_fill_price,
        }
