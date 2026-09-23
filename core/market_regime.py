class MarketRegimeEngine:
    """
    Classifies the current market regime from OHLC candle data.

    Regimes:
        - TRENDING_UP
        - TRENDING_DOWN
        - RANGING
        - TRANSITION

    The engine is deterministic and causal.

    It does not:
        - generate trading signals
        - approve trades
        - determine entries
        - determine stop losses
        - determine take profits
        - calculate position size
        - place orders
        - modify strategy parameters
    """

    def __init__(
        self,
        lookback=20,
        trend_threshold=0.02,
        trend_efficiency_threshold=0.60,
        transition_efficiency_threshold=0.20,
    ):
        if lookback < 1:
            raise ValueError(
                "lookback must be at least 1."
            )

        if trend_threshold <= 0:
            raise ValueError(
                "trend_threshold must be greater than 0."
            )

        if not 0 < trend_efficiency_threshold <= 1:
            raise ValueError(
                "trend_efficiency_threshold must be "
                "greater than 0 and at most 1."
            )

        if not 0 <= transition_efficiency_threshold <= 1:
            raise ValueError(
                "transition_efficiency_threshold must "
                "be between 0 and 1."
            )

        if (
            transition_efficiency_threshold
            >= trend_efficiency_threshold
        ):
            raise ValueError(
                "transition_efficiency_threshold must "
                "be lower than trend_efficiency_threshold."
            )

        self.lookback = int(lookback)
        self.trend_threshold = float(
            trend_threshold
        )
        self.trend_efficiency_threshold = float(
            trend_efficiency_threshold
        )
        self.transition_efficiency_threshold = float(
            transition_efficiency_threshold
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
        Validate candle data.
        """

        if not isinstance(candles, list):
            raise ValueError(
                "candles must be a list."
            )

        minimum_candles = (
            self.lookback + 1
        )

        if len(candles) < minimum_candles:
            raise ValueError(
                "Not enough candles to calculate "
                "market regime."
            )

        for candle in candles:
            if not isinstance(candle, dict):
                raise ValueError(
                    "Each candle must be a dictionary."
                )

            for field in (
                "open",
                "high",
                "low",
                "close",
                "volume",
            ):
                if field not in candle:
                    raise ValueError(
                        f"Missing candle {field}."
                    )

                if not self._is_number(
                    candle[field]
                ):
                    raise ValueError(
                        f"Invalid candle {field}."
                    )

            open_price = float(
                candle["open"]
            )
            high = float(
                candle["high"]
            )
            low = float(
                candle["low"]
            )
            close = float(
                candle["close"]
            )
            volume = float(
                candle["volume"]
            )

            if high < low:
                raise ValueError(
                    "Candle high cannot be below low."
                )

            if open_price <= 0:
                raise ValueError(
                    "Candle open must be greater than zero."
                )

            if high <= 0:
                raise ValueError(
                    "Candle high must be greater than zero."
                )

            if low <= 0:
                raise ValueError(
                    "Candle low must be greater than zero."
                )

            if close <= 0:
                raise ValueError(
                    "Candle close must be greater than zero."
                )

            if volume < 0:
                raise ValueError(
                    "Candle volume cannot be negative."
                )

        return True

    def _percentage_change(
        self,
        starting_close,
        ending_close,
    ):
        """
        Calculate signed percentage change.
        """

        if starting_close <= 0:
            raise ValueError(
                "Starting close must be greater than zero."
            )

        return (
            ending_close
            - starting_close
        ) / starting_close

    def directional_change(
        self,
        candles,
    ):
        """
        Calculate signed percentage change across
        the configured lookback period.
        """

        self._validate_candles(
            candles
        )

        latest_close = float(
            candles[-1]["close"]
        )

        starting_index = (
            len(candles)
            - self.lookback
            - 1
        )

        starting_close = float(
            candles[starting_index]["close"]
        )

        return self._percentage_change(
            starting_close,
            latest_close,
        )

    def efficiency_ratio(
        self,
        candles,
    ):
        """
        Calculate directional efficiency.

        Efficiency ratio:

            absolute net movement
            ---------------------
            total absolute movement

        A value near 1 means price moved persistently
        in one direction.

        A value near 0 means price moved back and forth.
        """

        self._validate_candles(
            candles
        )

        start_index = (
            len(candles)
            - self.lookback
            - 1
        )

        closes = [
            float(
                candles[index]["close"]
            )
            for index in range(
                start_index,
                len(candles),
            )
        ]

        net_movement = abs(
            closes[-1]
            - closes[0]
        )

        total_movement = 0.0

        for index in range(
            1,
            len(closes),
        ):
            total_movement += abs(
                closes[index]
                - closes[index - 1]
            )

        if total_movement == 0:
            return 0.0

        return (
            net_movement
            / total_movement
        )

    def directional_consistency(
        self,
        candles,
    ):
        """
        Measure how consistently candles move in the
        direction of the latest net movement.

        Returns a value between 0 and 1.
        """

        self._validate_candles(
            candles
        )

        start_index = (
            len(candles)
            - self.lookback
            - 1
        )

        start_close = float(
            candles[start_index]["close"]
        )

        latest_close = float(
            candles[-1]["close"]
        )

        if latest_close > start_close:
            direction = 1
        elif latest_close < start_close:
            direction = -1
        else:
            return 0.0

        agreeing_moves = 0
        total_moves = 0

        for index in range(
            start_index + 1,
            len(candles),
        ):
            current_close = float(
                candles[index]["close"]
            )

            previous_close = float(
                candles[index - 1]["close"]
            )

            movement = (
                current_close
                - previous_close
            )

            if movement == 0:
                continue

            total_moves += 1

            if (
                movement > 0
                and direction > 0
            ) or (
                movement < 0
                and direction < 0
            ):
                agreeing_moves += 1

        if total_moves == 0:
            return 0.0

        return (
            agreeing_moves
            / total_moves
        )

    def _broader_direction(
        self,
        candles,
    ):
        """
        Determine the broader directional movement.

        The broader window is the complete available
        history up to the current candle. It never uses
        future information.
        """

        first_close = float(
            candles[0]["close"]
        )

        latest_close = float(
            candles[-1]["close"]
        )

        return self._percentage_change(
            first_close,
            latest_close,
        )

    def classify(
        self,
        candles,
    ):
        """
        Classify the latest market regime.

        Logic:

            Strong recent directional movement
            + high efficiency
            + high consistency
                -> TRENDING_UP/DOWN

            Small recent movement
            + low efficiency
            + no meaningful broader direction
                -> RANGING

            Otherwise, when the market has directional
            development but lacks sufficient confirmation,
            classify it as TRANSITION.
        """

        self._validate_candles(
            candles
        )

        recent_change = (
            self.directional_change(
                candles
            )
        )

        efficiency = (
            self.efficiency_ratio(
                candles
            )
        )

        consistency = (
            self.directional_consistency(
                candles
            )
        )

        broader_change = (
            self._broader_direction(
                candles
            )
        )

        strong_uptrend = (
            recent_change
            >= self.trend_threshold
            and efficiency
            >= self.trend_efficiency_threshold
            and consistency
            >= self.trend_efficiency_threshold
        )

        strong_downtrend = (
            recent_change
            <= -self.trend_threshold
            and efficiency
            >= self.trend_efficiency_threshold
            and consistency
            >= self.trend_efficiency_threshold
        )

        if strong_uptrend:
            regime = "TRENDING_UP"

        elif strong_downtrend:
            regime = "TRENDING_DOWN"

        elif (
            abs(recent_change)
            < self.trend_threshold
            and abs(broader_change)
            < self.trend_threshold
            and efficiency
            <= self.transition_efficiency_threshold
        ):
            regime = "RANGING"

        else:
            regime = "TRANSITION"

        return {
            "regime": regime,
            "directional_change": recent_change,
            "efficiency_ratio": efficiency,
            "directional_consistency": consistency,
            "broader_directional_change": broader_change,
            "lookback": self.lookback,
            "trend_threshold": self.trend_threshold,
            "trend_efficiency_threshold": (
                self.trend_efficiency_threshold
            ),
            "transition_efficiency_threshold": (
                self.transition_efficiency_threshold
            ),
        }

    def analyze(
        self,
        candles,
    ):
        """
        Return the complete market regime analysis.
        """

        result = self.classify(
            candles
        )

        return {
            "status": "REGIME_ANALYZED",
            "regime": result[
                "regime"
            ],
            "directional_change": result[
                "directional_change"
            ],
            "efficiency_ratio": result[
                "efficiency_ratio"
            ],
            "directional_consistency": result[
                "directional_consistency"
            ],
            "broader_directional_change": result[
                "broader_directional_change"
            ],
            "lookback": result[
                "lookback"
            ],
            "trend_threshold": result[
                "trend_threshold"
            ],
            "trend_efficiency_threshold": result[
                "trend_efficiency_threshold"
            ],
            "transition_efficiency_threshold": result[
                "transition_efficiency_threshold"
            ],
        }