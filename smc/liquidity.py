class LiquidityEngine:
    """
    Detects liquidity pools, liquidity zones, and high-quality
    liquidity sweeps.

    Liquidity types:
    - Buy-side liquidity (BSL)
    - Sell-side liquidity (SSL)

    Sources:
    - Swing highs
    - Swing lows
    - Equal highs
    - Equal lows

    Sweep quality considers:
    - Liquidity penetration
    - ATR-relative excursion
    - Candle body size
    - Wick size
    - Close location
    - Rejection strength
    - Liquidity source count

    Important:
    This is an analysis engine, not a trading signal by itself.
    """

    def __init__(
        self,
        swing_length: int = 3,
        equal_tolerance_pct: float = 0.0005,
        zone_tolerance_pct: float = 0.001,
        atr_period: int = 14,
        max_sweep_atr_multiple: float = 0.75,
        max_sweep_distance_pct: float = 0.003,
        min_rejection_ratio: float = 0.20,
        max_close_distance_atr: float = 1.0,
    ):
        if swing_length < 1:
            raise ValueError(
                "swing_length must be at least 1."
            )

        if equal_tolerance_pct <= 0:
            raise ValueError(
                "equal_tolerance_pct must be greater than 0."
            )

        if zone_tolerance_pct <= 0:
            raise ValueError(
                "zone_tolerance_pct must be greater than 0."
            )

        if atr_period < 1:
            raise ValueError(
                "atr_period must be at least 1."
            )

        if max_sweep_atr_multiple <= 0:
            raise ValueError(
                "max_sweep_atr_multiple must be greater than 0."
            )

        if max_sweep_distance_pct <= 0:
            raise ValueError(
                "max_sweep_distance_pct must be greater than 0."
            )

        if not 0 <= min_rejection_ratio <= 1:
            raise ValueError(
                "min_rejection_ratio must be between 0 and 1."
            )

        if max_close_distance_atr <= 0:
            raise ValueError(
                "max_close_distance_atr must be greater than 0."
            )

        self.swing_length = swing_length
        self.equal_tolerance_pct = equal_tolerance_pct
        self.zone_tolerance_pct = zone_tolerance_pct
        self.atr_period = atr_period
        self.max_sweep_atr_multiple = max_sweep_atr_multiple
        self.max_sweep_distance_pct = max_sweep_distance_pct
        self.min_rejection_ratio = min_rejection_ratio
        self.max_close_distance_atr = max_close_distance_atr

    # ---------------------------------------------------------
    # PRICE COMPARISON HELPERS
    # ---------------------------------------------------------

    def _prices_are_equal(
        self,
        price_a: float,
        price_b: float,
    ) -> bool:
        """
        Check whether two prices are close enough to represent
        the same liquidity level.
        """

        difference = abs(price_a - price_b)
        average_price = (price_a + price_b) / 2

        if average_price == 0:
            return False

        difference_pct = difference / average_price

        return difference_pct <= self.equal_tolerance_pct

    def _price_is_near(
        self,
        price_a: float,
        price_b: float,
    ) -> bool:
        """
        Check whether two prices are close enough to belong
        to the same liquidity zone.
        """

        difference = abs(price_a - price_b)
        average_price = (price_a + price_b) / 2

        if average_price == 0:
            return False

        difference_pct = difference / average_price

        return difference_pct <= self.zone_tolerance_pct

    # ---------------------------------------------------------
    # ATR
    # ---------------------------------------------------------

    def calculate_atr(
        self,
        candles: list[dict],
    ) -> list[float | None]:
        """
        Calculate a simple Average True Range series.

        ATR is used to normalize sweep size according to
        current market volatility.
        """

        if not candles:
            return []

        true_ranges = [None] * len(candles)

        for i, candle in enumerate(candles):

            high = candle["high"]
            low = candle["low"]

            if i == 0:
                true_ranges[i] = high - low
                continue

            previous_close = candles[i - 1]["close"]

            true_range = max(
                high - low,
                abs(high - previous_close),
                abs(low - previous_close),
            )

            true_ranges[i] = true_range

        atr = [None] * len(candles)

        for i in range(len(candles)):

            start = i - self.atr_period + 1

            if start < 0:
                continue

            window = true_ranges[start:i + 1]

            if any(value is None for value in window):
                continue

            atr[i] = sum(window) / len(window)

        return atr

    # ---------------------------------------------------------
    # SWING DETECTION
    # ---------------------------------------------------------

    def detect_swings(
        self,
        candles: list[dict],
    ) -> list[dict]:
        """
        Detect confirmed swing highs and swing lows.
        """

        required = (self.swing_length * 2) + 1

        if len(candles) < required:
            raise ValueError(
                f"Need at least {required} candles."
            )

        swings = []
        length = self.swing_length

        for i in range(
            length,
            len(candles) - length,
        ):

            current = candles[i]

            left = candles[i - length:i]
            right = candles[i + 1:i + length + 1]

            current_high = current["high"]
            current_low = current["low"]

            is_swing_high = all(
                current_high > candle["high"]
                for candle in left + right
            )

            is_swing_low = all(
                current_low < candle["low"]
                for candle in left + right
            )

            # Ignore ambiguous candles.
            if is_swing_high and is_swing_low:
                continue

            if is_swing_high:

                swings.append(
                    {
                        "type": "swing_high",
                        "index": i,
                        "timestamp": current["timestamp"],
                        "price": current_high,
                    }
                )

            elif is_swing_low:

                swings.append(
                    {
                        "type": "swing_low",
                        "index": i,
                        "timestamp": current["timestamp"],
                        "price": current_low,
                    }
                )

        return swings

    # ---------------------------------------------------------
    # LIQUIDITY LEVELS
    # ---------------------------------------------------------

    def find_swing_liquidity(
        self,
        candles: list[dict],
    ) -> list[dict]:
        """
        Convert confirmed swing points into liquidity levels.
        """

        swings = self.detect_swings(candles)

        liquidity = []

        for swing in swings:

            if swing["type"] == "swing_high":

                liquidity.append(
                    {
                        "type": "buy_side",
                        "subtype": "swing_high",
                        "price": swing["price"],
                        "index": swing["index"],
                        "timestamp": swing["timestamp"],
                        "source": "swing",
                    }
                )

            else:

                liquidity.append(
                    {
                        "type": "sell_side",
                        "subtype": "swing_low",
                        "price": swing["price"],
                        "index": swing["index"],
                        "timestamp": swing["timestamp"],
                        "source": "swing",
                    }
                )

        return liquidity

    def find_equal_highs(
        self,
        candles: list[dict],
    ) -> list[dict]:
        """
        Detect consecutive swing highs that form equal-high
        liquidity.
        """

        swings = self.detect_swings(candles)

        highs = [
            swing
            for swing in swings
            if swing["type"] == "swing_high"
        ]

        equal_highs = []

        for i in range(len(highs) - 1):

            first = highs[i]
            second = highs[i + 1]

            if self._prices_are_equal(
                first["price"],
                second["price"],
            ):

                average_price = (
                    first["price"] + second["price"]
                ) / 2

                equal_highs.append(
                    {
                        "type": "buy_side",
                        "subtype": "equal_high",
                        "price": average_price,
                        "index": second["index"],
                        "timestamp": second["timestamp"],
                        "source": "equal_high",
                        "source_indices": [
                            first["index"],
                            second["index"],
                        ],
                    }
                )

        return equal_highs

    def find_equal_lows(
        self,
        candles: list[dict],
    ) -> list[dict]:
        """
        Detect consecutive swing lows that form equal-low
        liquidity.
        """

        swings = self.detect_swings(candles)

        lows = [
            swing
            for swing in swings
            if swing["type"] == "swing_low"
        ]

        equal_lows = []

        for i in range(len(lows) - 1):

            first = lows[i]
            second = lows[i + 1]

            if self._prices_are_equal(
                first["price"],
                second["price"],
            ):

                average_price = (
                    first["price"] + second["price"]
                ) / 2

                equal_lows.append(
                    {
                        "type": "sell_side",
                        "subtype": "equal_low",
                        "price": average_price,
                        "index": second["index"],
                        "timestamp": second["timestamp"],
                        "source": "equal_low",
                        "source_indices": [
                            first["index"],
                            second["index"],
                        ],
                    }
                )

        return equal_lows

    def find_all_liquidity(
        self,
        candles: list[dict],
    ) -> list[dict]:
        """
        Return all detected liquidity levels.
        """

        liquidity = []

        liquidity.extend(
            self.find_swing_liquidity(candles)
        )

        liquidity.extend(
            self.find_equal_highs(candles)
        )

        liquidity.extend(
            self.find_equal_lows(candles)
        )

        liquidity.sort(
            key=lambda level: level["index"]
        )

        return liquidity

    # ---------------------------------------------------------
    # LIQUIDITY ZONES
    # ---------------------------------------------------------

    def cluster_liquidity(
        self,
        liquidity_levels: list[dict],
    ) -> list[dict]:
        """
        Group nearby liquidity levels into liquidity zones.
        """

        if not liquidity_levels:
            return []

        sorted_levels = sorted(
            liquidity_levels,
            key=lambda level: (
                level["type"],
                level["price"],
            ),
        )

        zones = []

        for level in sorted_levels:

            matching_zone = None

            for zone in zones:

                if zone["type"] != level["type"]:
                    continue

                if self._price_is_near(
                    zone["price"],
                    level["price"],
                ):
                    matching_zone = zone
                    break

            if matching_zone is None:

                zones.append(
                    {
                        "type": level["type"],
                        "price": level["price"],
                        "high": level["price"],
                        "low": level["price"],
                        "index": level["index"],
                        "timestamp": level["timestamp"],
                        "sources": [level],
                    }
                )

            else:

                matching_zone["sources"].append(level)

                prices = [
                    source["price"]
                    for source in matching_zone["sources"]
                ]

                matching_zone["price"] = (
                    sum(prices) / len(prices)
                )

                matching_zone["high"] = max(prices)
                matching_zone["low"] = min(prices)

                matching_zone["index"] = max(
                    source["index"]
                    for source in matching_zone["sources"]
                )

        zones.sort(
            key=lambda zone: zone["index"]
        )

        return zones

    # ---------------------------------------------------------
    # SWEEP QUALITY
    # ---------------------------------------------------------

    def _evaluate_buy_side_sweep(
        self,
        candle: dict,
        zone: dict,
        atr: float | None,
    ) -> dict | None:
        """
        Evaluate a potential buy-side liquidity sweep.

        A valid bearish sweep requires:

        1. High penetrates the zone.
        2. Close returns below the liquidity zone.
        3. Excursion beyond the zone is not excessive.
        4. Close is not excessively far from the zone.
        5. The candle demonstrates rejection.
        """

        zone_high = zone["high"]
        zone_low = zone["low"]

        candle_high = candle["high"]
        candle_low = candle["low"]
        candle_close = candle["close"]
        candle_open = candle["open"]

        if candle_high <= zone_high:
            return None

        if candle_close >= zone_low:
            return None

        penetration = candle_high - zone_high

        if zone_high <= 0:
            return None

        penetration_pct = penetration / zone_high

        if penetration_pct > self.max_sweep_distance_pct:
            return None

        # ATR filter.
        if atr is not None and penetration > (
            atr * self.max_sweep_atr_multiple
        ):
            return None

        candle_range = candle_high - candle_low

        if candle_range <= 0:
            return None

        upper_wick = candle_high - max(
            candle_open,
            candle_close,
        )

        rejection_ratio = upper_wick / candle_range

        if rejection_ratio < self.min_rejection_ratio:
            return None

        # How far did the close travel below the zone?
        close_distance = zone_low - candle_close

        if atr is not None:
            close_distance_atr = close_distance / atr

            if close_distance_atr > self.max_close_distance_atr:
                return None
        else:
            close_distance_atr = None

        return {
            "type": "buy_side_sweep",
            "direction": "bearish",
            "penetration": penetration,
            "penetration_pct": penetration_pct,
            "close_distance": close_distance,
            "close_distance_atr": close_distance_atr,
            "rejection_ratio": rejection_ratio,
            "candle_range": candle_range,
            "atr": atr,
        }

    def _evaluate_sell_side_sweep(
        self,
        candle: dict,
        zone: dict,
        atr: float | None,
    ) -> dict | None:
        """
        Evaluate a potential sell-side liquidity sweep.

        A valid bullish sweep requires:

        1. Low penetrates the zone.
        2. Close returns above the liquidity zone.
        3. Excursion beyond the zone is not excessive.
        4. Close is not excessively far from the zone.
        5. The candle demonstrates rejection.
        """

        zone_high = zone["high"]
        zone_low = zone["low"]

        candle_high = candle["high"]
        candle_low = candle["low"]
        candle_close = candle["close"]
        candle_open = candle["open"]

        if candle_low >= zone_low:
            return None

        if candle_close <= zone_high:
            return None

        penetration = zone_low - candle_low

        if zone_low <= 0:
            return None

        penetration_pct = penetration / zone_low

        if penetration_pct > self.max_sweep_distance_pct:
            return None

        # ATR filter.
        if atr is not None and penetration > (
            atr * self.max_sweep_atr_multiple
        ):
            return None

        candle_range = candle_high - candle_low

        if candle_range <= 0:
            return None

        lower_wick = min(
            candle_open,
            candle_close,
        ) - candle_low

        rejection_ratio = lower_wick / candle_range

        if rejection_ratio < self.min_rejection_ratio:
            return None

        close_distance = candle_close - zone_high

        if atr is not None:
            close_distance_atr = close_distance / atr

            if close_distance_atr > self.max_close_distance_atr:
                return None
        else:
            close_distance_atr = None

        return {
            "type": "sell_side_sweep",
            "direction": "bullish",
            "penetration": penetration,
            "penetration_pct": penetration_pct,
            "close_distance": close_distance,
            "close_distance_atr": close_distance_atr,
            "rejection_ratio": rejection_ratio,
            "candle_range": candle_range,
            "atr": atr,
        }

    # ---------------------------------------------------------
    # SWEEP DETECTION
    # ---------------------------------------------------------

    def detect_sweeps(
        self,
        candles: list[dict],
        liquidity_levels: list[dict] | None = None,
    ) -> list[dict]:
        """
        Detect high-quality liquidity sweeps.

        Buy-side sweep:
            Price trades above buy-side liquidity,
            rejects, and closes back below the zone.

        Sell-side sweep:
            Price trades below sell-side liquidity,
            rejects, and closes back above the zone.

        Sweep quality is normalized using ATR where available.
        """

        if liquidity_levels is None:
            liquidity_levels = self.find_all_liquidity(
                candles
            )

        zones = self.cluster_liquidity(
            liquidity_levels
        )

        atr_values = self.calculate_atr(candles)

        sweeps = []

        for zone in zones:

            zone_index = zone["index"]

            for candle_index in range(
                zone_index + 1,
                len(candles),
            ):

                candle = candles[candle_index]

                atr = atr_values[candle_index]

                result = None

                if zone["type"] == "buy_side":

                    result = self._evaluate_buy_side_sweep(
                        candle,
                        zone,
                        atr,
                    )

                elif zone["type"] == "sell_side":

                    result = self._evaluate_sell_side_sweep(
                        candle,
                        zone,
                        atr,
                    )

                if result is None:
                    continue

                sweeps.append(
                    {
                        **result,
                        "candle_index": candle_index,
                        "timestamp": candle["timestamp"],
                        "price": candle["close"],
                        "liquidity_price": zone["price"],
                        "liquidity_high": zone["high"],
                        "liquidity_low": zone["low"],
                        "liquidity_index": zone_index,
                        "liquidity_sources": len(
                            zone["sources"]
                        ),
                    }
                )

                # First valid sweep consumes this zone.
                break

        sweeps.sort(
            key=lambda sweep: sweep["candle_index"]
        )

        return sweeps