class SetupEngine:
    """
    Combines SMC components into a causal trading setup.

    Pipeline:

        Liquidity Sweep
            ↓
        Displacement
            ↓
        Structure Confirmation
            ↓
        Order Block / FVG
            ↓
        Confluence Score
            ↓
        Setup Classification

    This engine does not execute trades.
    """

    def __init__(
        self,
        max_sweep_to_displacement=8,
        max_displacement_to_structure=5,
        max_structure_to_zone=8,
        minimum_confluence_score=70,
    ):
        self.max_sweep_to_displacement = (
            max_sweep_to_displacement
        )
        self.max_displacement_to_structure = (
            max_displacement_to_structure
        )
        self.max_structure_to_zone = (
            max_structure_to_zone
        )
        self.minimum_confluence_score = (
            minimum_confluence_score
        )

    def _direction_matches(
        self,
        first,
        second,
    ):
        return (
            first.get("direction")
            == second.get("direction")
        )

    def _opposite_direction(
        self,
        direction,
    ):
        if direction == "bullish":
            return "bearish"

        if direction == "bearish":
            return "bullish"

        return None

    def find_displacement_after_sweep(
        self,
        sweep,
        displacement,
    ):
        sweep_index = sweep.get(
            "candle_index"
        )

        sweep_direction = sweep.get(
            "direction"
        )

        if sweep_index is None:
            return None

        expected_direction = (
            self._opposite_direction(
                sweep_direction
            )
        )

        if expected_direction is None:
            return None

        for event in displacement:
            event_index = event.get(
                "candle_index"
            )

            if event_index is None:
                continue

            if event_index <= sweep_index:
                continue

            distance = (
                event_index
                - sweep_index
            )

            if (
                distance
                > self.max_sweep_to_displacement
            ):
                break

            if (
                event.get("direction")
                != expected_direction
            ):
                continue

            return event

        return None

    def find_structure_after_displacement(
        self,
        displacement_event,
        structure_breaks,
    ):
        displacement_index = (
            displacement_event.get(
                "candle_index"
            )
        )

        displacement_direction = (
            displacement_event.get(
                "direction"
            )
        )

        if displacement_index is None:
            return None

        for structure in structure_breaks:
            structure_index = structure.get(
                "candle_index"
            )

            if structure_index is None:
                continue

            if structure_index <= displacement_index:
                continue

            distance = (
                structure_index
                - displacement_index
            )

            if (
                distance
                > self.max_displacement_to_structure
            ):
                break

            if (
                structure.get("direction")
                != displacement_direction
            ):
                continue

            return structure

        return None

    def find_order_block(
        self,
        structure_event,
        order_blocks,
    ):
        """
        Find the context-eligible Order Block whose
        structural confirmation matches this structure event.
        """

        structure_index = structure_event.get(
            "candle_index"
        )

        structure_direction = structure_event.get(
            "direction"
        )

        if structure_index is None:
            return None

        if structure_direction is None:
            return None

        candidates = []

        for order_block in order_blocks:
            if not order_block.get(
                "context_eligible",
                False,
            ):
                continue

            if (
                order_block.get("direction")
                != structure_direction
            ):
                continue

            ob_index = order_block.get(
                "created_at_index"
            )

            if ob_index is None:
                continue

            if ob_index >= structure_index:
                continue

            context_structure_index = (
                order_block.get(
                    "structure_index"
                )
            )

            if (
                context_structure_index
                != structure_index
            ):
                continue

            candidates.append(
                order_block
            )

        if not candidates:
            return None

        candidates.sort(
            key=lambda item: (
                item.get(
                    "context_score",
                    0,
                ),
                item.get(
                    "quality_score",
                    0,
                ),
                item.get(
                    "created_at_index",
                    -1,
                ),
            ),
            reverse=True,
        )

        return candidates[0]

    def find_fvg(
        self,
        structure_event,
        fvgs,
    ):
        structure_index = structure_event.get(
            "candle_index"
        )

        structure_direction = structure_event.get(
            "direction"
        )

        if structure_index is None:
            return None

        if structure_direction is None:
            return None

        candidates = []

        for fvg in fvgs:
            if (
                fvg.get("status")
                == "invalidated"
            ):
                continue

            if not fvg.get(
                "eligible",
                False,
            ):
                continue

            fvg_index = fvg.get(
                "created_at_index"
            )

            if fvg_index is None:
                continue

            if fvg_index > structure_index:
                continue

            if (
                fvg.get("direction")
                != structure_direction
            ):
                continue

            distance = (
                structure_index
                - fvg_index
            )

            if (
                distance
                > self.max_structure_to_zone
            ):
                continue

            candidates.append(fvg)

        if not candidates:
            return None

        candidates.sort(
            key=lambda item: (
                item.get(
                    "quality_score",
                    0,
                ),
                item.get(
                    "created_at_index",
                    -1,
                ),
            ),
            reverse=True,
        )

        return candidates[0]

    def calculate_confluence_score(
        self,
        sweep,
        displacement,
        structure,
        order_block,
        fvg,
    ):
        score = 0

        if sweep is not None:
            score += 20

        if displacement is not None:
            score += 20

        if structure is not None:
            score += 20

        if order_block is not None:
            score += 20

        if fvg is not None:
            score += 20

        return score

    def evaluate_sweep(
        self,
        sweep,
        displacement,
        structure_breaks,
        order_blocks,
        fvgs,
    ):
        displacement_event = (
            self.find_displacement_after_sweep(
                sweep,
                displacement,
            )
        )

        if displacement_event is None:
            return {
                "sweep": sweep,
                "displacement": None,
                "structure": None,
                "order_block": None,
                "fvg": None,
                "setup_score": 20,
                "setup_status": "no_trade",
            }

        structure_event = (
            self.find_structure_after_displacement(
                displacement_event,
                structure_breaks,
            )
        )

        if structure_event is None:
            return {
                "sweep": sweep,
                "displacement": displacement_event,
                "structure": None,
                "order_block": None,
                "fvg": None,
                "setup_score": 40,
                "setup_status": "incomplete_setup",
            }

        order_block = self.find_order_block(
            structure_event,
            order_blocks,
        )

        fvg = self.find_fvg(
            structure_event,
            fvgs,
        )

        setup_score = (
            self.calculate_confluence_score(
                sweep,
                displacement_event,
                structure_event,
                order_block,
                fvg,
            )
        )

        if (
            order_block is not None
            and fvg is not None
            and setup_score
            >= self.minimum_confluence_score
        ):
            setup_status = "valid_setup"

        elif setup_score >= 40:
            setup_status = "incomplete_setup"

        else:
            setup_status = "no_trade"

        return {
            "sweep": sweep,
            "displacement": displacement_event,
            "structure": structure_event,
            "order_block": order_block,
            "fvg": fvg,
            "setup_score": setup_score,
            "setup_status": setup_status,
        }

    def evaluate_sweeps(
        self,
        sweeps,
        displacement,
        structure_breaks,
        order_blocks,
        fvgs,
    ):
        results = []

        for sweep in sweeps:
            results.append(
                self.evaluate_sweep(
                    sweep,
                    displacement,
                    structure_breaks,
                    order_blocks,
                    fvgs,
                )
            )

        return results

    def filter_valid_setups(
        self,
        setups,
    ):
        return [
            setup
            for setup in setups
            if setup.get("setup_status")
            == "valid_setup"
        ]