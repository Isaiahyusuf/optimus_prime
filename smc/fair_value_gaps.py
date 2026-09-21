class FairValueGapEngine:
    """
    Detects, tracks, and evaluates Fair Value Gaps (FVGs).

    This engine does NOT generate trade signals.
    """

    def __init__(
        self,
        min_gap_pct: float = 0.0001,
        max_gap_pct: float = 0.01,
        min_quality_score: int = 60,
    ):
        if min_gap_pct < 0:
            raise ValueError(
                "min_gap_pct cannot be negative."
            )

        if max_gap_pct <= 0:
            raise ValueError(
                "max_gap_pct must be greater than zero."
            )

        if min_gap_pct > max_gap_pct:
            raise ValueError(
                "min_gap_pct cannot exceed max_gap_pct."
            )

        if not 0 <= min_quality_score <= 100:
            raise ValueError(
                "min_quality_score must be between 0 and 100."
            )

        self.min_gap_pct = min_gap_pct
        self.max_gap_pct = max_gap_pct
        self.min_quality_score = min_quality_score

    # ==========================================================
    # FVG DETECTION
    # ==========================================================

    def detect_fvgs(
        self,
        candles: list[dict],
    ) -> list[dict]:
        """
        Detect raw FVGs from completed candles.
        """

        if len(candles) < 3:
            return []

        fvgs = []

        for i in range(2, len(candles)):

            first = candles[i - 2]
            middle = candles[i - 1]
            third = candles[i]

            # --------------------------------------------------
            # Bullish FVG
            # --------------------------------------------------

            if third["low"] > first["high"]:

                gap_low = first["high"]
                gap_high = third["low"]

                gap_size = gap_high - gap_low
                gap_pct = gap_size / gap_low

                if (
                    self.min_gap_pct
                    <= gap_pct
                    <= self.max_gap_pct
                ):
                    fvgs.append(
                        {
                            "type": "bullish_fvg",
                            "direction": "bullish",
                            "status": "active",
                            "created_at_index": i,
                            "created_timestamp": third[
                                "timestamp"
                            ],
                            "gap_low": gap_low,
                            "gap_high": gap_high,
                            "gap_size": gap_size,
                            "gap_pct": gap_pct,
                            "first_candle_index": i - 2,
                            "middle_candle_index": i - 1,
                            "third_candle_index": i,
                        }
                    )

            # --------------------------------------------------
            # Bearish FVG
            # --------------------------------------------------

            if third["high"] < first["low"]:

                gap_low = third["high"]
                gap_high = first["low"]

                gap_size = gap_high - gap_low
                gap_pct = gap_size / gap_high

                if (
                    self.min_gap_pct
                    <= gap_pct
                    <= self.max_gap_pct
                ):
                    fvgs.append(
                        {
                            "type": "bearish_fvg",
                            "direction": "bearish",
                            "status": "active",
                            "created_at_index": i,
                            "created_timestamp": third[
                                "timestamp"
                            ],
                            "gap_low": gap_low,
                            "gap_high": gap_high,
                            "gap_size": gap_size,
                            "gap_pct": gap_pct,
                            "first_candle_index": i - 2,
                            "middle_candle_index": i - 1,
                            "third_candle_index": i,
                        }
                    )

        return fvgs

    # ==========================================================
    # FVG LIFECYCLE
    # ==========================================================

    def update_fvg_status(
        self,
        fvg: dict,
        candles: list[dict],
    ) -> dict:
        """
        Track how price interacts with an FVG after creation.
        """

        updated = dict(fvg)

        creation_index = fvg["created_at_index"]

        gap_low = fvg["gap_low"]
        gap_high = fvg["gap_high"]

        gap_size = gap_high - gap_low

        status = "active"

        max_fill = 0.0

        mitigation_index = None
        mitigation_timestamp = None

        invalidation_index = None
        invalidation_timestamp = None

        for i in range(
            creation_index + 1,
            len(candles),
        ):

            candle = candles[i]

            if fvg["direction"] == "bullish":

                # Price enters bullish FVG.
                if candle["low"] < gap_high:

                    fill_low = max(
                        candle["low"],
                        gap_low,
                    )

                    filled_distance = (
                        gap_high - fill_low
                    )

                    fill_percentage = (
                        filled_distance / gap_size
                    )

                    max_fill = max(
                        max_fill,
                        min(fill_percentage, 1.0),
                    )

                    if mitigation_index is None:
                        mitigation_index = i
                        mitigation_timestamp = (
                            candle["timestamp"]
                        )

                # Full invalidation.
                if candle["low"] <= gap_low:

                    status = "invalidated"

                    invalidation_index = i
                    invalidation_timestamp = (
                        candle["timestamp"]
                    )

                    break

            else:

                # Price enters bearish FVG.
                if candle["high"] > gap_low:

                    fill_high = min(
                        candle["high"],
                        gap_high,
                    )

                    filled_distance = (
                        fill_high - gap_low
                    )

                    fill_percentage = (
                        filled_distance / gap_size
                    )

                    max_fill = max(
                        max_fill,
                        min(fill_percentage, 1.0),
                    )

                    if mitigation_index is None:
                        mitigation_index = i
                        mitigation_timestamp = (
                            candle["timestamp"]
                        )

                # Full invalidation.
                if candle["high"] >= gap_high:

                    status = "invalidated"

                    invalidation_index = i
                    invalidation_timestamp = (
                        candle["timestamp"]
                    )

                    break

        if (
            status == "active"
            and mitigation_index is not None
        ):
            if max_fill >= 1.0:
                status = "mitigated"
            else:
                status = "partially_mitigated"

        updated["status"] = status

        updated["max_fill_percentage"] = max_fill

        updated["mitigation_index"] = (
            mitigation_index
        )

        updated["mitigation_timestamp"] = (
            mitigation_timestamp
        )

        updated["invalidation_index"] = (
            invalidation_index
        )

        updated["invalidation_timestamp"] = (
            invalidation_timestamp
        )

        return updated

    # ==========================================================
    # CANDLE QUALITY
    # ==========================================================

    def _candle_body_ratio(
        self,
        candle: dict,
    ) -> float:
        """
        Measures candle body relative to total range.
        """

        candle_range = (
            candle["high"] - candle["low"]
        )

        if candle_range <= 0:
            return 0.0

        body = abs(
            candle["close"] - candle["open"]
        )

        return body / candle_range

    def _close_location(
        self,
        candle: dict,
    ) -> float:
        """
        Measures where the close sits inside the candle.

        1.0 = close at high
        0.0 = close at low
        """

        candle_range = (
            candle["high"] - candle["low"]
        )

        if candle_range <= 0:
            return 0.5

        return (
            candle["close"] - candle["low"]
        ) / candle_range

    # ==========================================================
    # FVG QUALITY
    # ==========================================================

    def evaluate_quality(
        self,
        fvg: dict,
        candles: list[dict],
    ) -> dict:
        """
        Evaluate the structural quality of an FVG.

        This is a quality assessment only.
        It does NOT produce a trading signal.

        Score components:

            Gap size       = 25 points
            Candle quality = 30 points
            Freshness      = 20 points
            Lifecycle      = 25 points

        Total = 100 points
        """

        if not candles:
            raise ValueError(
                "candles cannot be empty."
            )

        updated = self.update_fvg_status(
            fvg,
            candles,
        )

        creation_index = fvg[
            "created_at_index"
        ]

        if creation_index >= len(candles):
            raise ValueError(
                "FVG creation index exceeds candle data."
            )

        first = candles[
            fvg["first_candle_index"]
        ]

        middle = candles[
            fvg["middle_candle_index"]
        ]

        third = candles[
            fvg["third_candle_index"]
        ]

        # ------------------------------------------------------
        # 1. GAP SIZE — 25 POINTS
        # ------------------------------------------------------

        gap_pct = fvg["gap_pct"]

        if gap_pct >= 0.0020:
            gap_score = 25
        elif gap_pct >= 0.0010:
            gap_score = 20
        elif gap_pct >= 0.0005:
            gap_score = 15
        elif gap_pct >= 0.0002:
            gap_score = 10
        else:
            gap_score = 5

        # ------------------------------------------------------
        # 2. CANDLE QUALITY — 30 POINTS
        # ------------------------------------------------------

        body_ratio = self._candle_body_ratio(
            middle
        )

        close_location = self._close_location(
            middle
        )

        candle_score = 0

        if body_ratio >= 0.70:
            candle_score += 15
        elif body_ratio >= 0.55:
            candle_score += 10
        elif body_ratio >= 0.40:
            candle_score += 5

        if fvg["direction"] == "bullish":

            if close_location >= 0.80:
                candle_score += 15
            elif close_location >= 0.65:
                candle_score += 10
            elif close_location >= 0.50:
                candle_score += 5

        else:

            bearish_close_location = (
                1.0 - close_location
            )

            if bearish_close_location >= 0.80:
                candle_score += 15
            elif bearish_close_location >= 0.65:
                candle_score += 10
            elif bearish_close_location >= 0.50:
                candle_score += 5

        # ------------------------------------------------------
        # 3. FRESHNESS — 20 POINTS
        # ------------------------------------------------------

        status = updated["status"]
        fill = updated[
            "max_fill_percentage"
        ]

        if status == "active":
            freshness_score = 20
        elif (
            status == "partially_mitigated"
            and fill <= 0.50
        ):
            freshness_score = 15
        elif (
            status == "partially_mitigated"
            and fill <= 0.75
        ):
            freshness_score = 10
        elif (
            status == "partially_mitigated"
            and fill < 1.0
        ):
            freshness_score = 5
        else:
            freshness_score = 0

        # ------------------------------------------------------
        # 4. LIFECYCLE — 25 POINTS
        # ------------------------------------------------------

        if status == "active":
            lifecycle_score = 25
        elif status == "partially_mitigated":
            lifecycle_score = 15
        elif status == "mitigated":
            lifecycle_score = 5
        else:
            lifecycle_score = 0

        # ------------------------------------------------------
        # FINAL SCORE
        # ------------------------------------------------------

        total_score = (
            gap_score
            + candle_score
            + freshness_score
            + lifecycle_score
        )

        if total_score >= 80:
            quality = "A"
        elif total_score >= 70:
            quality = "B"
        elif total_score >= 60:
            quality = "C"
        else:
            quality = "D"

        result = dict(updated)

        result["quality_score"] = total_score
        result["quality_grade"] = quality

        result["quality_components"] = {
            "gap_score": gap_score,
            "candle_score": candle_score,
            "freshness_score": freshness_score,
            "lifecycle_score": lifecycle_score,
        }

        result["middle_candle_body_ratio"] = (
            body_ratio
        )

        result["middle_candle_close_location"] = (
            close_location
        )

        result["eligible"] = (
            total_score
            >= self.min_quality_score
            and status != "invalidated"
            and fill < 0.90
        )

        return result

    # ==========================================================
    # QUALITY FILTER
    # ==========================================================

    def filter_quality_fvgs(
        self,
        fvgs: list[dict],
        candles: list[dict],
    ) -> list[dict]:
        """
        Evaluate all FVGs and return only eligible FVGs.

        This does NOT create trade signals.
        """

        quality_fvgs = []

        for fvg in fvgs:

            evaluated = self.evaluate_quality(
                fvg,
                candles,
            )

            if evaluated["eligible"]:
                quality_fvgs.append(
                    evaluated
                )

        return quality_fvgs
