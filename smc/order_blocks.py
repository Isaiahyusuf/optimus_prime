from __future__ import annotations

from typing import Any


class OrderBlockEngine:
    """
    Causal Order Block detection and quality evaluation engine.

    An Order Block is the final opposing candle before a meaningful
    directional displacement.

    Important:
    Historical evaluation must only use information available up to the
    evaluation candle. This prevents look-ahead bias in backtesting.

    Lifecycle rules:

    Bullish OB:
        - Wick entering the zone = mitigation
        - Close below OB low = invalidation

    Bearish OB:
        - Wick entering the zone = mitigation
        - Close above OB high = invalidation

    The displacement candle that confirms the Order Block is NOT treated
    as a mitigation candle. Lifecycle evaluation begins after displacement.

    Detection and quality are intentionally separated:

        Detection
            ↓
        Raw Order Block
            ↓
        Quality Evaluation
            ↓
        Context Confirmation
            ↓
        Setup Engine

    A weak opposing candle may still be a valid raw Order Block candidate.
    Its candle quality is evaluated separately during quality scoring.
    """

    def __init__(
        self,
        confirmation_window: int = 3,
        min_body_ratio: float = 0.40,
        max_mitigation_pct: float = 0.80,
    ):
        self.confirmation_window = confirmation_window
        self.min_body_ratio = min_body_ratio
        self.max_mitigation_pct = max_mitigation_pct

    # ------------------------------------------------------------------
    # Candle helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _body_ratio(candle: dict[str, Any]) -> float:
        candle_range = (
            float(candle["high"])
            - float(candle["low"])
        )

        if candle_range <= 0:
            return 0.0

        return abs(
            float(candle["close"])
            - float(candle["open"])
        ) / candle_range

    @staticmethod
    def _is_bullish(candle: dict[str, Any]) -> bool:
        return float(candle["close"]) > float(candle["open"])

    @staticmethod
    def _is_bearish(candle: dict[str, Any]) -> bool:
        return float(candle["close"]) < float(candle["open"])

    # ------------------------------------------------------------------
    # Order Block detection
    # ------------------------------------------------------------------

    def detect_order_blocks(
        self,
        candles: list[dict[str, Any]],
        displacement: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Detect the final opposing candle before displacement.

        Bullish displacement:
            final bearish candle before displacement = bullish OB

        Bearish displacement:
            final bullish candle before displacement = bearish OB

        Body ratio is NOT a hard detection requirement.

        A candle can therefore become a raw OB candidate even when its
        body is relatively small. Candle quality is evaluated later.
        """

        order_blocks: list[dict[str, Any]] = []

        if not candles or not displacement:
            return order_blocks

        candle_by_index = {
            index: candle
            for index, candle in enumerate(candles)
        }

        for event in displacement:
            displacement_index = event.get("candle_index")
            direction = event.get("direction")

            if displacement_index is None:
                continue

            if displacement_index <= 0:
                continue

            if displacement_index not in candle_by_index:
                continue

            if direction not in {"bullish", "bearish"}:
                continue

            start_index = max(
                0,
                displacement_index
                - self.confirmation_window,
            )

            candidate_index = None

            # ----------------------------------------------------------
            # Search backward for the final opposing candle.
            # ----------------------------------------------------------

            for index in range(
                displacement_index - 1,
                start_index - 1,
                -1,
            ):
                candle = candle_by_index[index]

                if (
                    direction == "bullish"
                    and self._is_bearish(candle)
                ):
                    candidate_index = index
                    break

                if (
                    direction == "bearish"
                    and self._is_bullish(candle)
                ):
                    candidate_index = index
                    break

            if candidate_index is None:
                continue

            candidate = candle_by_index[candidate_index]

            body_ratio = self._body_ratio(candidate)

            # ----------------------------------------------------------
            # IMPORTANT:
            #
            # Do NOT reject the candidate because of body ratio here.
            #
            # The opposing candle is structurally identified first.
            # Its body quality is scored later by evaluate_quality().
            # ----------------------------------------------------------

            order_blocks.append(
                {
                    "type": "order_block",
                    "direction": direction,
                    "created_at_index": candidate_index,
                    "displacement_index": displacement_index,
                    "timestamp": candidate["timestamp"],
                    "open": candidate["open"],
                    "high": candidate["high"],
                    "low": candidate["low"],
                    "close": candidate["close"],
                    "body_ratio": body_ratio,
                    "status": "created",
                    "fill_percentage": 0.0,
                    "invalidated_at_index": None,
                }
            )

        return order_blocks

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def update_order_block_status(
        self,
        order_block: dict[str, Any],
        candles: list[dict[str, Any]],
        evaluation_index: int | None = None,
    ) -> dict[str, Any]:
        """
        Evaluate Order Block lifecycle causally.

        The originating displacement candle is excluded from lifecycle
        mitigation/invalidation checks.

        Only candles AFTER the displacement candle can change the
        Order Block lifecycle.

        Bullish OB:
            wick into zone -> mitigation
            close below OB low -> invalidation

        Bearish OB:
            wick into zone -> mitigation
            close above OB high -> invalidation
        """

        if not candles:
            return {
                **order_block,
                "status": "created",
                "fill_percentage": 0.0,
                "invalidated_at_index": None,
            }

        created_index = int(
            order_block["created_at_index"]
        )

        displacement_index = int(
            order_block["displacement_index"]
        )

        if evaluation_index is None:
            evaluation_index = len(candles) - 1

        evaluation_index = max(
            displacement_index,
            min(
                int(evaluation_index),
                len(candles) - 1,
            ),
        )

        direction = order_block["direction"]

        ob_high = float(order_block["high"])
        ob_low = float(order_block["low"])

        ob_range = ob_high - ob_low

        if ob_range <= 0:
            return {
                **order_block,
                "status": "invalidated",
                "fill_percentage": 1.0,
                "invalidated_at_index": created_index,
            }

        status = "active"
        fill_percentage = 0.0
        invalidated_at_index = None

        # --------------------------------------------------------------
        # IMPORTANT:
        #
        # Start AFTER displacement.
        #
        # The displacement candle confirms the Order Block.
        # It must not immediately mitigate or invalidate the same OB.
        # --------------------------------------------------------------

        lifecycle_start = displacement_index + 1

        if lifecycle_start > evaluation_index:
            return {
                **order_block,
                "status": "active",
                "fill_percentage": 0.0,
                "invalidated_at_index": None,
            }

        for index in range(
            lifecycle_start,
            evaluation_index + 1,
        ):
            candle = candles[index]

            candle_high = float(candle["high"])
            candle_low = float(candle["low"])
            candle_close = float(candle["close"])

            # ----------------------------------------------------------
            # Bullish Order Block
            # ----------------------------------------------------------

            if direction == "bullish":

                # A close below the OB invalidates it.
                if candle_close < ob_low:
                    status = "invalidated"
                    fill_percentage = 1.0
                    invalidated_at_index = index
                    break

                # Wick penetration is mitigation.
                penetration = max(
                    0.0,
                    min(
                        ob_range,
                        ob_high - candle_low,
                    ),
                )

                current_fill = penetration / ob_range

                fill_percentage = max(
                    fill_percentage,
                    current_fill,
                )

            # ----------------------------------------------------------
            # Bearish Order Block
            # ----------------------------------------------------------

            elif direction == "bearish":

                # A close above the OB invalidates it.
                if candle_close > ob_high:
                    status = "invalidated"
                    fill_percentage = 1.0
                    invalidated_at_index = index
                    break

                # Wick penetration is mitigation.
                penetration = max(
                    0.0,
                    min(
                        ob_range,
                        candle_high - ob_low,
                    ),
                )

                current_fill = penetration / ob_range

                fill_percentage = max(
                    fill_percentage,
                    current_fill,
                )

        # --------------------------------------------------------------
        # Determine lifecycle state
        # --------------------------------------------------------------

        if status != "invalidated":

            if fill_percentage >= 1.0:
                status = "mitigated"

            elif fill_percentage > 0.0:
                status = "partially_mitigated"

            else:
                status = "active"

        return {
            **order_block,
            "status": status,
            "fill_percentage": round(
                fill_percentage,
                6,
            ),
            "invalidated_at_index": invalidated_at_index,
        }

    # ------------------------------------------------------------------
    # Quality evaluation
    # ------------------------------------------------------------------

    def evaluate_quality(
        self,
        order_block: dict[str, Any],
        candles: list[dict[str, Any]],
        evaluation_index: int | None = None,
    ) -> dict[str, Any]:
        """
        Evaluate Order Block quality at a specific point in time.

        No candle after evaluation_index can influence the result.

        For a setup that requires displacement confirmation, callers
        should normally evaluate at the structure-confirmation candle.
        """

        if not candles:
            return {
                **order_block,
                "quality_score": 0,
                "quality_grade": "D",
                "eligible": False,
                "evaluation_index": None,
            }

        if evaluation_index is None:
            evaluation_index = len(candles) - 1

        evaluation_index = max(
            int(order_block["displacement_index"]),
            min(
                int(evaluation_index),
                len(candles) - 1,
            ),
        )

        updated = self.update_order_block_status(
            order_block,
            candles,
            evaluation_index=evaluation_index,
        )

        score = 0

        # --------------------------------------------------------------
        # 1. Candle quality — 30 points
        # --------------------------------------------------------------

        body_ratio = float(
            order_block.get("body_ratio", 0.0)
        )

        if body_ratio >= 0.70:
            score += 30

        elif body_ratio >= 0.55:
            score += 20

        elif body_ratio >= self.min_body_ratio:
            score += 10

        # --------------------------------------------------------------
        # 2. Proximity to displacement — 25 points
        # --------------------------------------------------------------

        ob_index = int(
            order_block["created_at_index"]
        )

        displacement_index = int(
            order_block["displacement_index"]
        )

        distance = (
            displacement_index
            - ob_index
        )

        if distance == 1:
            score += 25

        elif distance == 2:
            score += 20

        elif distance == 3:
            score += 10

        # --------------------------------------------------------------
        # 3. Freshness — 20 points
        # --------------------------------------------------------------

        age = max(
            0,
            evaluation_index - ob_index,
        )

        if age <= 5:
            score += 20

        elif age <= 10:
            score += 15

        elif age <= 20:
            score += 10

        elif age <= 40:
            score += 5

        # --------------------------------------------------------------
        # 4. Lifecycle — 25 points
        # --------------------------------------------------------------

        status = updated["status"]

        fill_percentage = float(
            updated["fill_percentage"]
        )

        if status == "active":
            score += 25

        elif status == "partially_mitigated":

            if fill_percentage <= 0.30:
                score += 20

            elif fill_percentage <= 0.50:
                score += 15

            elif fill_percentage <= self.max_mitigation_pct:
                score += 10

        elif status == "mitigated":
            score += 0

        elif status == "invalidated":
            score += 0

        # --------------------------------------------------------------
        # Grade
        # --------------------------------------------------------------

        if score >= 80:
            grade = "A"

        elif score >= 70:
            grade = "B"

        elif score >= 60:
            grade = "C"

        else:
            grade = "D"

        # --------------------------------------------------------------
        # Eligibility
        # --------------------------------------------------------------

        eligible = (
            score >= 60
            and status != "invalidated"
            and fill_percentage
            < self.max_mitigation_pct
        )

        return {
            **updated,
            "quality_score": score,
            "quality_grade": grade,
            "eligible": eligible,
            "evaluation_index": evaluation_index,
        }

    # ------------------------------------------------------------------
    # Quality filtering
    # ------------------------------------------------------------------

    def filter_quality_order_blocks(
        self,
        order_blocks: list[dict[str, Any]],
        candles: list[dict[str, Any]],
        evaluation_index: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return Order Blocks that pass quality requirements.

        evaluation_index allows historical/backtest callers to evaluate
        Order Blocks using only information available at that point.
        """

        qualified: list[dict[str, Any]] = []

        for order_block in order_blocks:

            evaluated = self.evaluate_quality(
                order_block,
                candles,
                evaluation_index=evaluation_index,
            )

            if evaluated["eligible"]:
                qualified.append(evaluated)

        return qualified