from decimal import Decimal, ROUND_DOWN


class OrderEngine:
    """
    Normalize Guardian-approved trade plans into exchange-valid
    order parameters.

    This layer does not place orders.
    """

    def __init__(self, exchange):
        self.exchange = exchange

    def _get_instrument(self, symbol: str) -> dict:
        instruments = self.exchange.get_instrument_info(symbol)

        if not instruments:
            raise RuntimeError(
                f"No instrument information found for {symbol}."
            )

        return instruments[0]

    @staticmethod
    def _floor_to_step(value: Decimal, step: Decimal) -> Decimal:
        if step <= 0:
            raise ValueError("Step size must be positive.")

        return (value / step).to_integral_value(
            rounding=ROUND_DOWN,
        ) * step

    def normalize_quantity(self, symbol: str, quantity: float | str) -> str:
        """
        Normalize order quantity to the symbol's exchange quantity step.
        """

        instrument = self._get_instrument(symbol)
        lot_size = instrument["lotSizeFilter"]

        qty = Decimal(str(quantity))
        step = Decimal(lot_size["qtyStep"])
        minimum = Decimal(lot_size["minOrderQty"])

        if qty <= 0:
            raise ValueError("Order quantity must be positive.")

        normalized = self._floor_to_step(qty, step)

        if normalized < minimum:
            raise ValueError(
                f"Order quantity {normalized} is below minimum "
                f"quantity {minimum} for {symbol}."
            )

        return format(normalized, "f")

    def normalize_price(self, symbol: str, price: float | str) -> str:
        """
        Normalize an order price to the symbol's exchange price tick.
        """

        instrument = self._get_instrument(symbol)
        price_filter = instrument["priceFilter"]

        value = Decimal(str(price))
        tick_size = Decimal(price_filter["tickSize"])
        minimum = Decimal(price_filter["minPrice"])
        maximum = Decimal(price_filter["maxPrice"])

        if value <= 0:
            raise ValueError("Order price must be positive.")

        normalized = self._floor_to_step(value, tick_size)

        if normalized < minimum:
            raise ValueError(
                f"Order price {normalized} is below minimum "
                f"price {minimum} for {symbol}."
            )

        if normalized > maximum:
            raise ValueError(
                f"Order price {normalized} exceeds maximum "
                f"price {maximum} for {symbol}."
            )

        return format(normalized, "f")

    def validate_minimum_notional(
        self,
        symbol: str,
        quantity: float | str,
        price: float | str,
    ) -> str:
        """
        Validate that an order meets the exchange minimum notional value.
        """

        instrument = self._get_instrument(symbol)
        minimum_notional = Decimal(
            instrument["lotSizeFilter"]["minNotionalValue"]
        )

        normalized_quantity = Decimal(
            self.normalize_quantity(symbol, quantity)
        )
        normalized_price = Decimal(
            self.normalize_price(symbol, price)
        )

        notional = normalized_quantity * normalized_price

        if notional < minimum_notional:
            raise ValueError(
                f"Order notional {notional} is below minimum "
                f"notional {minimum_notional} for {symbol}."
            )

        return format(notional, "f")

    def validate_max_quantity(
        self,
        symbol: str,
        quantity: float | str,
    ) -> str:
        """
        Validate that an order quantity does not exceed the exchange maximum.
        """

        instrument = self._get_instrument(symbol)
        lot_size = instrument["lotSizeFilter"]

        normalized_quantity = Decimal(
            self.normalize_quantity(symbol, quantity)
        )
        maximum = Decimal(lot_size["maxOrderQty"])

        if normalized_quantity > maximum:
            raise ValueError(
                f"Order quantity {normalized_quantity} exceeds maximum "
                f"quantity {maximum} for {symbol}."
            )

        return format(normalized_quantity, "f")

    def validate_price_range(
        self,
        symbol: str,
        price: float | str,
    ) -> str:
        """
        Validate that an order price is within the exchange price range.
        """

        instrument = self._get_instrument(symbol)
        price_filter = instrument["priceFilter"]

        normalized_price = Decimal(
            self.normalize_price(symbol, price)
        )
        minimum = Decimal(price_filter["minPrice"])
        maximum = Decimal(price_filter["maxPrice"])

        if normalized_price < minimum:
            raise ValueError(
                f"Order price {normalized_price} is below minimum "
                f"price {minimum} for {symbol}."
            )

        if normalized_price > maximum:
            raise ValueError(
                f"Order price {normalized_price} exceeds maximum "
                f"price {maximum} for {symbol}."
            )

        return format(normalized_price, "f")

    def prepare_quantity(
        self,
        symbol: str,
        trade_plan: dict,
    ) -> str:
        """
        Prepare the Guardian-approved position size for exchange submission.

        This method does not recalculate position size or risk.
        It only validates and normalizes the quantity against exchange rules.
        """

        if not isinstance(trade_plan, dict):
            raise ValueError("Trade plan must be a dictionary.")

        if trade_plan.get("status") != "GUARDIAN_APPROVED":
            raise ValueError(
                "Only GUARDIAN_APPROVED trade plans can be prepared."
            )

        quantity = trade_plan.get("position_size")

        if quantity is None:
            raise ValueError(
                "Guardian-approved trade plan is missing position_size."
            )

        normalized_quantity = self.normalize_quantity(
            symbol,
            quantity,
        )

        self.validate_max_quantity(
            symbol,
            normalized_quantity,
        )

        return normalized_quantity

    def prepare_prices(
        self,
        symbol: str,
        trade_plan: dict,
    ) -> dict:
        """
        Prepare Guardian-approved entry, stop-loss, and take-profit prices.

        This method only normalizes exchange precision and does not
        recalculate or alter the Guardian trade plan.
        """

        if not isinstance(trade_plan, dict):
            raise ValueError("Trade plan must be a dictionary.")

        if trade_plan.get("status") != "GUARDIAN_APPROVED":
            raise ValueError(
                "Only GUARDIAN_APPROVED trade plans can be prepared."
            )

        required_prices = {
            "entry_price": trade_plan.get("entry_price"),
            "stop_loss": trade_plan.get("stop_loss"),
            "take_profit": trade_plan.get("take_profit"),
        }

        missing = [
            name for name, value in required_prices.items()
            if value is None
        ]

        if missing:
            raise ValueError(
                f"Guardian-approved trade plan is missing: "
                f"{', '.join(missing)}."
            )

        return {
            "entry_price": self.normalize_price(
                symbol,
                required_prices["entry_price"],
            ),
            "stop_loss": self.normalize_price(
                symbol,
                required_prices["stop_loss"],
            ),
            "take_profit": self.normalize_price(
                symbol,
                required_prices["take_profit"],
            ),
        }

    def prepare_order(
        self,
        symbol: str,
        trade_plan: dict,
    ) -> dict:
        """
        Convert a Guardian-approved trade plan into an exchange-ready
        order payload without submitting the order.
        """

        if not isinstance(trade_plan, dict):
            raise ValueError("Trade plan must be a dictionary.")

        if trade_plan.get("status") != "GUARDIAN_APPROVED":
            raise ValueError(
                "Only GUARDIAN_APPROVED trade plans can be prepared."
            )

        direction = str(
            trade_plan.get("direction", "")
        ).lower()

        if direction in {"long", "bullish", "buy"}:
            side = "Buy"
        elif direction in {"short", "bearish", "sell"}:
            side = "Sell"
        else:
            raise ValueError(
                f"Unsupported trade direction: {trade_plan.get('direction')}"
            )

        quantity = self.prepare_quantity(symbol, trade_plan)
        prices = self.prepare_prices(symbol, trade_plan)

        self.validate_minimum_notional(
            symbol,
            quantity,
            prices["entry_price"],
        )

        self.validate_order_geometry(
            side,
            prices["entry_price"],
            prices["stop_loss"],
            prices["take_profit"],
        )

        return {
            "category": "linear",
            "symbol": symbol.upper(),
            "side": side,
            "orderType": "Limit",
            "qty": quantity,
            "price": prices["entry_price"],
            "stopLoss": prices["stop_loss"],
            "takeProfit": prices["take_profit"],
        }

    def validate_order_geometry(
        self,
        side: str,
        entry_price: float | str,
        stop_loss: float | str,
        take_profit: float | str,
    ) -> bool:
        """
        Validate the final exchange-normalized order geometry.
        """

        entry = Decimal(str(entry_price))
        stop = Decimal(str(stop_loss))
        target = Decimal(str(take_profit))

        if entry <= 0 or stop <= 0 or target <= 0:
            raise ValueError("Order prices must be positive.")

        if side == "Buy":
            if not (stop < entry < target):
                raise ValueError(
                    "Invalid Buy order geometry: "
                    "stop_loss < entry_price < take_profit is required."
                )

        elif side == "Sell":
            if not (target < entry < stop):
                raise ValueError(
                    "Invalid Sell order geometry: "
                    "take_profit < entry_price < stop_loss is required."
                )

        else:
            raise ValueError(
                f"Unsupported order side: {side}"
            )

        return True

    def prepare_protection_orders(
        self,
        symbol: str,
        trade_plan: dict,
    ) -> dict:
        """
        Prepare a Bybit V5 trading-stop payload for an existing position.

        This method does not submit anything. The payload is intended for
        Bybit's /v5/position/trading-stop endpoint.
        """

        if not isinstance(trade_plan, dict):
            raise ValueError("Trade plan must be a dictionary.")

        if trade_plan.get("status") != "GUARDIAN_APPROVED":
            raise ValueError(
                "Only GUARDIAN_APPROVED trade plans can be prepared."
            )

        direction = str(
            trade_plan.get("direction", "")
        ).lower()

        if direction in {"long", "bullish", "buy"}:
            position_idx = 0
        elif direction in {"short", "bearish", "sell"}:
            position_idx = 0
        else:
            raise ValueError(
                f"Unsupported trade direction: {trade_plan.get('direction')}"
            )

        prices = self.prepare_prices(symbol, trade_plan)

        entry = prices["entry_price"]
        stop_loss = prices["stop_loss"]
        take_profit = prices["take_profit"]

        self.validate_order_geometry(
            "Buy" if direction in {"long", "bullish", "buy"} else "Sell",
            entry,
            stop_loss,
            take_profit,
        )

        return {
            "category": "linear",
            "symbol": symbol.upper(),
            "tpslMode": "Full",
            "positionIdx": position_idx,
            "stopLoss": stop_loss,
            "takeProfit": take_profit,
            "slTriggerBy": "MarkPrice",
            "tpTriggerBy": "MarkPrice",
        }
