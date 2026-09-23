class VolatilityEngine:
    """
    Calculates market volatility from OHLC candle data.

    Responsibilities:
        - validate candle data
        - calculate True Range
        - calculate ATR
        - calculate normalized ATR percentage
        - classify current volatility

    This class does not:
        - generate trading signals
        - determine market direction
        - place orders
        - calculate position size
        - modify trading strategy
    """

    def __init__(
        self,
        atr_period=14,
        low_threshold=0.5,
        high_threshold=2.0,
    ):
        if atr_period < 1:
            raise ValueError(
                "atr_period must be at least 1."
            )

        if low_threshold < 0:
            raise ValueError(
                "low_threshold cannot be negative."
            )

        if high_threshold <= low_threshold:
            raise ValueError(
                "high_threshold must be greater than "
                "low_threshold."
            )

        self.atr_period = int(atr_period)
        self.low_threshold = float(
            low_threshold
        )
        self.high_threshold = float(
            high_threshold
        )

    def _is_number(self, value):
        """
        Return True when value is a finite number.
        """

        try:
            number = float(value)
        except (
            TypeError,
            ValueError,
        ):
            return False

        if number != number:
            return False

        if number == float("inf"):
            return False

        if number == float("-inf"):
            return False

        return True

    def _validate_candles(self, candles):
        """
        Validate the candle collection.

        Candles must contain numeric:
            - high
            - low
            - close
        """

        if not isinstance(candles, list):
            raise ValueError(
                "candles must be a list."
            )

        if len(candles) < self.atr_period:
            raise ValueError(
                "Not enough candles to calculate ATR."
            )

        for candle in candles:
            if not isinstance(candle, dict):
                raise ValueError(
                    "Each candle must be a dictionary."
                )

            for field in (
                "high",
                "low",
                "close",
            ):
                if not self._is_number(
                    candle.get(field)
                ):
                    raise ValueError(
                        f"Invalid candle {field}."
                    )

            high = float(candle["high"])
            low = float(candle["low"])
            close = float(candle["close"])

            if high < low:
                raise ValueError(
                    "Candle high cannot be below low."
                )

            if close < 0:
                raise ValueError(
                    "Candle close cannot be negative."
                )

        return True

    def true_range(
        self,
        candles,
    ):
        """
        Calculate True Range for every candle.

        The first candle uses:
            high - low

        Every later candle uses:
            max(
                high - low,
                abs(high - previous_close),
                abs(low - previous_close),
            )
        """

        self._validate_candles(candles)

        ranges = []

        for index, candle in enumerate(candles):
            high = float(candle["high"])
            low = float(candle["low"])

            if index == 0:
                previous_close = None
            else:
                previous_close = float(
                    candles[index - 1]["close"]
                )

            if previous_close is None:
                current_range = high - low
            else:
                current_range = max(
                    high - low,
                    abs(high - previous_close),
                    abs(low - previous_close),
                )

            ranges.append(current_range)

        return ranges

    def atr(
        self,
        candles,
    ):
        """
        Calculate simple moving-average ATR.

        The returned list contains one ATR value for
        every candle where enough historical True Range
        values are available.

        Each ATR uses only current and previous candles.
        """

        ranges = self.true_range(candles)

        atr_values = []

        for index in range(
            self.atr_period - 1,
            len(ranges),
        ):
            window_start = (
                index - self.atr_period + 1
            )

            window = ranges[
                window_start : index + 1
            ]

            atr_value = (
                sum(window)
                / self.atr_period
            )

            atr_values.append(
                atr_value
            )

        return atr_values

    def atr_percent(
        self,
        candles,
    ):
        """
        Calculate ATR as a percentage of closing price.

        Formula:

            ATR% = ATR / Close * 100

        Only candles with a corresponding ATR value
        are returned.
        """

        self._validate_candles(candles)

        atr_values = self.atr(candles)

        percentages = []

        first_atr_index = (
            self.atr_period - 1
        )

        for offset, atr_value in enumerate(
            atr_values
        ):
            candle_index = (
                first_atr_index + offset
            )

            close = float(
                candles[candle_index]["close"]
            )

            if close <= 0:
                raise ValueError(
                    "Candle close must be greater "
                    "than zero for ATR%."
                )

            percentage = (
                atr_value
                / close
                * 100.0
            )

            percentages.append(
                percentage
            )

        return percentages

    def classify(
        self,
        candles,
    ):
        """
        Classify the latest available volatility.

        Returns one of:
            LOW
            NORMAL
            HIGH
        """

        percentages = self.atr_percent(
            candles
        )

        latest = percentages[-1]

        if latest < self.low_threshold:
            classification = "LOW"
        elif latest >= self.high_threshold:
            classification = "HIGH"
        else:
            classification = "NORMAL"

        return {
            "atr": self.atr(candles)[-1],
            "atr_percent": latest,
            "classification": classification,
            "period": self.atr_period,
        }

    def analyze(
        self,
        candles,
    ):
        """
        Return the complete latest volatility analysis.
        """

        result = self.classify(candles)

        return {
            "status": "VOLATILITY_ANALYZED",
            "atr": result["atr"],
            "atr_percent": result[
                "atr_percent"
            ],
            "classification": result[
                "classification"
            ],
            "period": result["period"],
        }