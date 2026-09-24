from execution.order_state import OrderState


class OrderLifecycle:
    """
    Converts normalized exchange order state into TradeRecord entry states.

    This layer does not query or modify exchange state.
    It only interprets one already-retrieved order.
    """

    ENTRY_STATE_MAP = {
        "PENDING": "ENTRY_PENDING",
        "PARTIALLY_FILLED": "ENTRY_PARTIALLY_FILLED",
        "FILLED": "ENTRY_FILLED",
        "CANCELLED": "ENTRY_CANCELLED",
        "REJECTED": "ENTRY_REJECTED",
        "UNKNOWN": "ENTRY_STATE_UNKNOWN",
    }

    def __init__(self, order_state=None):
        self.order_state = order_state or OrderState()

    def interpret(self, order: dict) -> str:
        """
        Return the corresponding TradeRecord entry state.
        """

        normalized_state = self.order_state.interpret(order)

        return self.ENTRY_STATE_MAP[normalized_state]

    def get_execution_data(self, order: dict) -> dict:
        """
        Return normalized execution quantities and fill price.
        """

        return self.order_state.get_execution_data(order)

    def interpret_with_execution(self, order: dict) -> dict:
        """
        Return lifecycle state together with normalized execution data.

        Execution data is optional because some exchange responses may
        provide order status without execution quantities. When execution
        data is present, it must be consistent with the lifecycle state.
        """

        state = self.interpret(order)

        execution_fields = {
            "qty",
            "cumExecQty",
            "leavesQty",
            "avgPrice",
        }

        if not execution_fields.issubset(order):
            return {
                "state": state,
                "execution": None,
            }

        execution = self.get_execution_data(order)

        order_quantity = execution["order_quantity"]
        filled_quantity = execution["filled_quantity"]
        remaining_quantity = execution["remaining_quantity"]

        tolerance = 1e-12

        if abs(
            order_quantity
            - (filled_quantity + remaining_quantity)
        ) > tolerance:
            raise ValueError(
                "Execution quantities are inconsistent."
            )

        if state == "ENTRY_FILLED":
            if (
                abs(filled_quantity - order_quantity) > tolerance
                or abs(remaining_quantity) > tolerance
            ):
                raise ValueError(
                    "Filled order execution data is inconsistent."
                )

        elif state == "ENTRY_PARTIALLY_FILLED":
            if not (
                filled_quantity > tolerance
                and filled_quantity < order_quantity - tolerance
                and remaining_quantity > tolerance
            ):
                raise ValueError(
                    "Partially filled order execution data is inconsistent."
                )

        elif state == "ENTRY_PENDING":
            if filled_quantity > tolerance:
                raise ValueError(
                    "Pending order execution data is inconsistent."
                )

        return {
            "state": state,
            "execution": execution,
        }
