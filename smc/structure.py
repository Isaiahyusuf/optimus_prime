class MarketStructure:
    """
    Causal market-structure engine.

    Detects:
    - Confirmed swing highs/lows
    - HH / HL / LH / LL classification
    - BOS
    - MSS

    IMPORTANT:

    A swing requires `swing_length` candles on both sides.

    Therefore, a swing at candle N only becomes known after
    candle N + swing_length has closed.

    This prevents future-candle look-ahead bias.
    """

    def __init__(self, swing_length: int = 3):
        if swing_length < 1:
            raise ValueError(
                "swing_length must be at least 1."
            )

        self.swing_length = swing_length

    # ==========================================================
    # SWING DETECTION
    # ==========================================================

    def detect_swings(
        self,
        candles: list[dict],
    ) -> list[dict]:
        """
        Detect confirmed swings without look-ahead bias.

        A swing at index N is confirmed at:

            N + swing_length

        The returned swing therefore records:

            index
            confirmed_at_index

        The confirmation index is the earliest candle at which
        the swing could have been known.
        """

        required = (
            self.swing_length * 2
        ) + 1

        if len(candles) < required:
            raise ValueError(
                f"Need at least {required} candles."
            )

        swings = []

        length = self.swing_length

        # ------------------------------------------------------
        # The final `length` candles cannot be confirmed because
        # their required right-side candles do not exist yet.
        # ------------------------------------------------------

        for i in range(
            length,
            len(candles) - length,
        ):

            current = candles[i]

            left = candles[
                i - length:i
            ]

            right = candles[
                i + 1:i + length + 1
            ]

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

            # --------------------------------------------------
            # Ambiguous candle.
            # --------------------------------------------------

            if (
                is_swing_high
                and is_swing_low
            ):
                continue

            confirmation_index = (
                i + length
            )

            # --------------------------------------------------
            # Swing High
            # --------------------------------------------------

            if is_swing_high:

                swings.append(
                    {
                        "type": "swing_high",
                        "index": i,
                        "confirmed_at_index": (
                            confirmation_index
                        ),
                        "timestamp": (
                            current["timestamp"]
                        ),
                        "confirmation_timestamp": (
                            candles[
                                confirmation_index
                            ]["timestamp"]
                        ),
                        "price": current_high,
                    }
                )

            # --------------------------------------------------
            # Swing Low
            # --------------------------------------------------

            elif is_swing_low:

                swings.append(
                    {
                        "type": "swing_low",
                        "index": i,
                        "confirmed_at_index": (
                            confirmation_index
                        ),
                        "timestamp": (
                            current["timestamp"]
                        ),
                        "confirmation_timestamp": (
                            candles[
                                confirmation_index
                            ]["timestamp"]
                        ),
                        "price": current_low,
                    }
                )

        return swings

    # ==========================================================
    # STRUCTURE CLASSIFICATION
    # ==========================================================

    def classify_structure(
        self,
        candles: list[dict],
    ) -> list[dict]:
        """
        Classify confirmed swings as:

        Highs:
            HH = Higher High
            LH = Lower High

        Lows:
            HL = Higher Low
            LL = Lower Low

        Classification itself does not use future information
        beyond the swing's confirmation point.
        """

        swings = self.detect_swings(
            candles
        )

        previous_high = None
        previous_low = None

        structure = []

        for swing in swings:

            if swing["type"] == "swing_high":

                if previous_high is None:
                    label = "SH"

                elif (
                    swing["price"]
                    > previous_high
                ):
                    label = "HH"

                else:
                    label = "LH"

                previous_high = swing[
                    "price"
                ]

            else:

                if previous_low is None:
                    label = "SL"

                elif (
                    swing["price"]
                    > previous_low
                ):
                    label = "HL"

                else:
                    label = "LL"

                previous_low = swing[
                    "price"
                ]

            structure.append(
                {
                    **swing,
                    "label": label,
                }
            )

        return structure

    # ==========================================================
    # BREAK DETECTION
    # ==========================================================

    def detect_breaks(
        self,
        candles: list[dict],
    ) -> list[dict]:
        """
        Detect BOS and MSS chronologically.

        A structural level can only be used after its swing has
        actually been confirmed.

        Rules:

        1. Only confirmed swings become structural levels.
        2. A swing cannot be used before confirmed_at_index.
        3. Break requires candle CLOSE beyond the level.
        4. Each structural level can only be broken once.
        5. First directional break is MSS.
        6. Continuation in same direction is BOS.
        7. Opposite directional break is MSS.
        """

        structure = self.classify_structure(
            candles
        )

        if not structure:
            return []

        breaks = []

        bias = None

        active_high = None
        active_low = None

        broken_high_indices = set()
        broken_low_indices = set()

        # ------------------------------------------------------
        # Process candles chronologically.
        # ------------------------------------------------------

        for candle_index, candle in enumerate(
            candles
        ):

            close = candle["close"]

            # --------------------------------------------------
            # Activate only swings that are confirmed by the
            # CURRENT candle.
            # --------------------------------------------------

            for swing in structure:

                if (
                    swing["confirmed_at_index"]
                    != candle_index
                ):
                    continue

                if swing["type"] == "swing_high":

                    active_high = swing

                elif swing["type"] == "swing_low":

                    active_low = swing

            # --------------------------------------------------
            # Bullish break.
            # --------------------------------------------------

            if (
                active_high is not None
                and active_high["index"]
                not in broken_high_indices
                and close
                > active_high["price"]
                and candle_index
                > active_high[
                    "confirmed_at_index"
                ]
            ):

                if bias == "bullish":
                    event_type = "BOS"
                else:
                    event_type = "MSS"

                breaks.append(
                    {
                        "type": event_type,
                        "direction": "bullish",
                        "candle_index": (
                            candle_index
                        ),
                        "timestamp": (
                            candle["timestamp"]
                        ),
                        "price": close,
                        "broken_level": (
                            active_high[
                                "price"
                            ]
                        ),
                        "broken_swing_index": (
                            active_high[
                                "index"
                            ]
                        ),
                        "broken_swing_confirmed_at": (
                            active_high[
                                "confirmed_at_index"
                            ]
                        ),
                    }
                )

                broken_high_indices.add(
                    active_high["index"]
                )

                bias = "bullish"

                active_high = None

            # --------------------------------------------------
            # Bearish break.
            # --------------------------------------------------

            if (
                active_low is not None
                and active_low["index"]
                not in broken_low_indices
                and close
                < active_low["price"]
                and candle_index
                > active_low[
                    "confirmed_at_index"
                ]
            ):

                if bias == "bearish":
                    event_type = "BOS"
                else:
                    event_type = "MSS"

                breaks.append(
                    {
                        "type": event_type,
                        "direction": "bearish",
                        "candle_index": (
                            candle_index
                        ),
                        "timestamp": (
                            candle["timestamp"]
                        ),
                        "price": close,
                        "broken_level": (
                            active_low[
                                "price"
                            ]
                        ),
                        "broken_swing_index": (
                            active_low[
                                "index"
                            ]
                        ),
                        "broken_swing_confirmed_at": (
                            active_low[
                                "confirmed_at_index"
                            ]
                        ),
                    }
                )

                broken_low_indices.add(
                    active_low["index"]
                )

                bias = "bearish"

                active_low = None

        return breaks
