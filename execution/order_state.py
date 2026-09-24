class OrderState:
    """
    Interprets exchange order statuses into normalized execution states.

    This layer does not query or modify exchange state.
    """

    STATUS_MAP = {
        "New": "PENDING",
        "PartiallyFilled": "PARTIALLY_FILLED",
        "Filled": "FILLED",
        "Cancelled": "CANCELLED",
        "Rejected": "REJECTED",
    }

    def interpret(self, order: dict) -> str:
        """
        Return a normalized execution state for an exchange order.
        """

        if not isinstance(order, dict):
            raise ValueError("Order must be a dictionary.")

        status = order.get("orderStatus")

        if not status:
            raise ValueError("Order status is required.")

        return self.STATUS_MAP.get(status, "UNKNOWN")
