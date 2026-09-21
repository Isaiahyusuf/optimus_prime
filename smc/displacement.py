class DisplacementEngine:
    """
    Detects directional price displacement.

    Displacement is treated as an impulsive price movement with
    meaningful range, body strength, and directional conviction.

    The engine evaluates:
    - Candle range relative to ATR
    - Candle body relative to range
    - Close location within the candle
    - Directional consistency
    - Consecutive candles
    """

    def __init__(
        self,
        atr_period: int = 14,
        min_range_atr: float = 1.0,
        min_body_ratio: float = 0.60,
        min_close_location: float = 0.70,
        max_opposite_wick_ratio: float = 0.30,
        consecutive_candles: int = 2,
    ):
        if atr_period < 1:
            raise ValueError(
                "atr_period must be at least 1."
            )

        if min_range_atr <= 0:
            raise ValueError(
                "min_range_atr must be greater than 0."
            )

        if not 0 < min_body_ratio <= 1:
            raise ValueError(
                "min_body_ratio must be between 0 and 1."
            )

        if not 0 < min_close_location <= 1:
            raise ValueError(
                "min_close_location must be between 0 and 1."
            )

        if not 0 <= max_opposite_wick_ratio <= 1:
            raise ValueError(
                "max_opposite_wick_ratio must be between 0 and 1."
            )

        if consecutive_candles < 1:
            raise ValueError(
                "consecutive_candles must be at least 1."
            )

        self.atr_period = atr_period
        self.min_range_atr = min_range_atr
        self.min_body_ratio = min_body_ratio
        self.min_close_location = min_close_location
        self.max_opposite_wick_ratio = max_opposite_wick_ratio
        self.consecutive_candles = consecutive_candles

    # ---------------------------------------------------------
    # ATR
    # ---------------------------------------------------------

    def calculate_atr(
        self,
        candles: list[dict],
    ) -> list[float | None]:
        """
        Calculate simple ATR.
        """

        if not candles:
            return []

        true_ranges = []

        for i, candle in enumerate(candles):

            high = candle["high"]
            low = candle["low"]

            if i == 0:

                true_range = high - low

            else:

                previous_close = candles[i - 1]["close"]

                true_range = max(
                    high - low,
                    abs(high - previous_close),
                    abs(low - previous_close),
                )

            true_ranges.append(true_range)

        atr = [None] * len(candles)

        for i in range(len(candles)):

            start = i - self.atr_period + 1

            if start < 0:
                continue

            window = true_ranges[start:i + 1]

            atr[i] = sum(window) / len(window)

        return atr

    # ---------------------------------------------------------
    # SINGLE CANDLE ANALYSIS
    # ---------------------------------------------------------

    def analyze_candle(
        self,
        candle: dict,
        atr: float | None,
    ) -> dict:
        """
        Analyze the strength and direction of one candle.
        """

        candle_open = candle["open"]
        candle_high = candle["high"]
        candle_low = candle["low"]
        candle_close = candle["close"]

        candle_range = candle_high - candle_low

        if candle_range <= 0:
            return {
                "direction": "neutral",
                "range": 0.0,
                "body": 0.0,
                "body_ratio": 0.0,
                "close_location": 0.5,
                "opposite_wick_ratio": 0.0,
                "range_atr": None,
                "valid": False,
            }

        body = abs(
            candle_close - candle_open
        )

        body_ratio = body / candle_range

        close_location = (
            candle_close - candle_low
        ) / candle_range

        upper_wick = (
            candle_high
            - max(candle_open, candle_close)
        )

        lower_wick = (
            min(candle_open, candle_close)
            - candle_low
        )

        if candle_close > candle_open:

            direction = "bullish"

            opposite_wick = upper_wick

        elif candle_close < candle_open:

            direction = "bearish"

            opposite_wick = lower_wick

        else:

            direction = "neutral"

            opposite_wick = max(
                upper_wick,
                lower_wick,
            )

        opposite_wick_ratio = (
            opposite_wick / candle_range
        )

        if atr is not None and atr > 0:

            range_atr = candle_range / atr

        else:

            range_atr = None

        valid = True

        return {
            "direction": direction,
            "range": candle_range,
            "body": body,
            "body_ratio": body_ratio,
            "close_location": close_location,
            "opposite_wick_ratio": opposite_wick_ratio,
            "range_atr": range_atr,
            "upper_wick": upper_wick,
            "lower_wick": lower_wick,
            "valid": valid,
        }

    # ---------------------------------------------------------
    # DISPLACEMENT VALIDATION
    # ---------------------------------------------------------

    def _is_valid_bullish_displacement(
        self,
        analysis: dict,
    ) -> bool:
        """
        Determine whether candle represents strong bullish
        displacement.
        """

        if analysis["direction"] != "bullish":
            return False

        if analysis["range_atr"] is None:
            return False

        if analysis["range_atr"] < self.min_range_atr:
            return False

        if analysis["body_ratio"] < self.min_body_ratio:
            return False

        if (
            analysis["close_location"]
            < self.min_close_location
        ):
            return False

        if (
            analysis["opposite_wick_ratio"]
            > self.max_opposite_wick_ratio
        ):
            return False

        return True

    def _is_valid_bearish_displacement(
        self,
        analysis: dict,
    ) -> bool:
        """
        Determine whether candle represents strong bearish
        displacement.
        """

        if analysis["direction"] != "bearish":
            return False

        if analysis["range_atr"] is None:
            return False

        if analysis["range_atr"] < self.min_range_atr:
            return False

        if analysis["body_ratio"] < self.min_body_ratio:
            return False

        if (
            analysis["close_location"]
            > (1 - self.min_close_location)
        ):
            return False

        if (
            analysis["opposite_wick_ratio"]
            > self.max_opposite_wick_ratio
        ):
            return False

        return True

    # ---------------------------------------------------------
    # DISPLACEMENT DETECTION
    # ---------------------------------------------------------

    def detect_displacement(
        self,
        candles: list[dict],
    ) -> list[dict]:
        """
        Detect individual displacement candles.
        """

        if not candles:
            return []

        atr_values = self.calculate_atr(candles)

        displacement = []

        for i, candle in enumerate(candles):

            analysis = self.analyze_candle(
                candle,
                atr_values[i],
            )

            bullish = (
                self._is_valid_bullish_displacement(
                    analysis
                )
            )

            bearish = (
                self._is_valid_bearish_displacement(
                    analysis
                )
            )

            if not bullish and not bearish:
                continue

            direction = (
                "bullish"
                if bullish
                else "bearish"
            )

            displacement.append(
                {
                    "type": "displacement",
                    "direction": direction,
                    "candle_index": i,
                    "timestamp": candle["timestamp"],
                    "open": candle["open"],
                    "high": candle["high"],
                    "low": candle["low"],
                    "close": candle["close"],
                    "range": analysis["range"],
                    "body": analysis["body"],
                    "body_ratio": analysis["body_ratio"],
                    "close_location": analysis[
                        "close_location"
                    ],
                    "opposite_wick_ratio": analysis[
                        "opposite_wick_ratio"
                    ],
                    "range_atr": analysis["range_atr"],
                    "atr": atr_values[i],
                }
            )

        return displacement

    # ---------------------------------------------------------
    # CONSECUTIVE DISPLACEMENT
    # ---------------------------------------------------------

    def detect_impulses(
        self,
        candles: list[dict],
    ) -> list[dict]:
        """
        Detect sequences of consecutive displacement candles
        moving in the same direction.
        """

        displacement = self.detect_displacement(
            candles
        )

        if not displacement:
            return []

        by_index = {
            item["candle_index"]: item
            for item in displacement
        }

        impulses = []

        i = 0

        while i < len(candles):

            if i not in by_index:

                i += 1
                continue

            first = by_index[i]
            direction = first["direction"]

            sequence = [first]

            next_index = i + 1

            while (
                next_index in by_index
                and by_index[next_index]["direction"]
                == direction
            ):

                sequence.append(
                    by_index[next_index]
                )

                next_index += 1

            if len(sequence) >= self.consecutive_candles:

                impulses.append(
                    {
                        "type": "displacement_impulse",
                        "direction": direction,
                        "start_index": sequence[0][
                            "candle_index"
                        ],
                        "end_index": sequence[-1][
                            "candle_index"
                        ],
                        "start_timestamp": sequence[0][
                            "timestamp"
                        ],
                        "end_timestamp": sequence[-1][
                            "timestamp"
                        ],
                        "candles": len(sequence),
                        "range": (
                            candles[
                                sequence[-1]["candle_index"]
                            ]["high"]
                            - candles[
                                sequence[0]["candle_index"]
                            ]["low"]
                            if direction == "bullish"
                            else candles[
                                sequence[0]["candle_index"]
                            ]["high"]
                            - candles[
                                sequence[-1]["candle_index"]
                            ]["low"]
                        ),
                        "members": sequence,
                    }
                )

            i = next_index

        return impulses