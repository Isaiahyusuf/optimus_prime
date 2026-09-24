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

    def get_execution_data(self, order: dict) -> dict:
        """
        Extract normalized execution quantities and average fill price.

        This method does not query or modify exchange state.
        """

        if not isinstance(order, dict):
            raise ValueError("Order must be a dictionary.")

        def parse_number(value, field_name):
            if value is None:
                raise ValueError(
                    f"{field_name} is required."
                )

            try:
                return float(value)
            except (TypeError, ValueError):
                raise ValueError(
                    f"{field_name} must be numeric."
                )

        order_quantity = parse_number(
            order.get("qty"),
            "Order quantity",
        )

        filled_quantity = parse_number(
            order.get("cumExecQty"),
            "Cumulative executed quantity",
        )

        remaining_quantity = parse_number(
            order.get("leavesQty"),
            "Remaining quantity",
        )

        average_fill_price = parse_number(
            order.get("avgPrice"),
            "Average fill price",
        )

        if order_quantity < 0:
            raise ValueError("Order quantity cannot be negative.")

        if filled_quantity < 0:
            raise ValueError(
                "Cumulative executed quantity cannot be negative."
            )

        if remaining_quantity < 0:
            raise ValueError(
                "Remaining quantity cannot be negative."
            )

        if average_fill_price < 0:
            raise ValueError(
                "Average fill price cannot be negative."
            )

        return {
            "order_quantity": order_quantity,
            "filled_quantity": filled_quantity,
            "remaining_quantity": remaining_quantity,
            "average_fill_price": average_fill_price,
        }
