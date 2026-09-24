class PositionManager:
    """
    Read-only position-state manager.

    This layer observes exchange positions and normalizes their state.
    It does not place, modify, or close orders.
    """

    def __init__(self, exchange):
        self.exchange = exchange

    def get_position(self, symbol: str) -> dict | None:
        """
        Return the active exchange position for a symbol, if one exists.
        """

        if not symbol:
            raise ValueError("Symbol is required.")

        return self.exchange.get_position(symbol.upper())

    def has_position(self, symbol: str) -> bool:
        """
        Return True when an active position exists for the symbol.
        """

        return self.get_position(symbol) is not None

    def reconcile_position(
        self,
        symbol: str,
        expected_side: str | None = None,
        expected_size: float = 0.0,
    ) -> dict:
        """
        Compare expected position state with actual exchange state.

        This method is read-only. It never opens, modifies, or closes
        a position.
        """

        if not symbol:
            raise ValueError("Symbol is required.")

        symbol = symbol.upper()

        if expected_side is not None:
            expected_side = expected_side.capitalize()

            if expected_side not in {"Buy", "Sell"}:
                raise ValueError(
                    "Expected side must be Buy, Sell, or None."
                )

        if expected_size < 0:
            raise ValueError(
                "Expected size cannot be negative."
            )

        actual = self.get_position_state(symbol)

        if expected_size == 0:
            if not actual["has_position"]:
                status = "MATCH"
            else:
                status = "UNEXPECTED_POSITION"

        elif not actual["has_position"]:
            status = "MISSING_POSITION"

        elif expected_side is not None and actual["side"] != expected_side:
            status = "POSITION_MISMATCH"

        elif abs(actual["size"] - expected_size) > max(
            1e-12,
            abs(expected_size) * 1e-9,
        ):
            status = "SIZE_MISMATCH"

        else:
            status = "MATCH"

        return {
            "symbol": symbol,
            "status": status,
            "expected_side": expected_side,
            "expected_size": expected_size,
            "actual_side": actual["side"],
            "actual_size": actual["size"],
            "actual_entry_price": actual["entry_price"],
            "actual_unrealized_pnl": actual["unrealized_pnl"],
        }

    def get_position_state(self, symbol: str) -> dict:
        """
        Return a normalized read-only representation of the
        exchange position state.
        """

        position = self.get_position(symbol)

        if position is None:
            return {
                "symbol": symbol.upper(),
                "has_position": False,
                "side": None,
                "size": 0.0,
                "entry_price": 0.0,
                "unrealized_pnl": 0.0,
            }

        side = position.get("side")
        raw_size = position.get("size", "0")
        raw_entry_price = position.get("avgPrice", "0")
        raw_unrealized_pnl = position.get(
            "unrealisedPnl",
            "0",
        )

        try:
            size = float(raw_size)
        except (TypeError, ValueError):
            size = 0.0

        try:
            entry_price = float(raw_entry_price)
        except (TypeError, ValueError):
            entry_price = 0.0

        try:
            unrealized_pnl = float(raw_unrealized_pnl)
        except (TypeError, ValueError):
            unrealized_pnl = 0.0

        return {
            "symbol": symbol.upper(),
            "has_position": size > 0,
            "side": side,
            "size": size,
            "entry_price": entry_price,
            "unrealized_pnl": unrealized_pnl,
        }

    def get_protection_state(self, symbol: str) -> dict:
        """
        Return the normalized TP/SL protection state reported by the
        exchange for the active position.

        This method is read-only. It never applies, modifies, or
        removes protection.
        """

        if not symbol:
            raise ValueError("Symbol is required.")

        symbol = symbol.upper()
        position = self.get_position(symbol)

        if position is None:
            return {
                "symbol": symbol,
                "has_position": False,
                "has_stop_loss": False,
                "has_take_profit": False,
                "stop_loss": None,
                "take_profit": None,
            }

        raw_stop_loss = position.get("stopLoss")
        raw_take_profit = position.get("takeProfit")

        def parse_optional_price(value, field_name):
            if value in {None, ""}:
                return None

            try:
                price = float(value)
            except (TypeError, ValueError):
                raise ValueError(
                    f"{field_name} must be numeric when provided."
                )

            if price <= 0:
                raise ValueError(
                    f"{field_name} must be greater than zero when provided."
                )

            return price

        stop_loss = parse_optional_price(
            raw_stop_loss,
            "Stop loss",
        )

        take_profit = parse_optional_price(
            raw_take_profit,
            "Take profit",
        )

        return {
            "symbol": symbol,
            "has_position": True,
            "has_stop_loss": stop_loss is not None,
            "has_take_profit": take_profit is not None,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }
