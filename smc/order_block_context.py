class OrderBlockContextEngine:
    """
    Adds structural context to detected order blocks.

    This engine does not create trade signals.
    It only determines whether an order block has
    sufficient displacement and structure confirmation.
    """

    def __init__(
        self,
        max_displacement_distance=3,
        max_structure_confirmation_window=5,
        minimum_context_score=60,
    ):
        self.max_displacement_distance = max_displacement_distance
        self.max_structure_confirmation_window = (
            max_structure_confirmation_window
        )
        self.minimum_context_score = minimum_context_score

    def _find_structure_confirmation(
        self,
        order_block,
        structure_breaks,
    ):
        displacement_index = order_block.get(
            "displacement_index"
        )

        if displacement_index is None:
            return None

        direction = order_block.get("direction")

        for structure in structure_breaks:
            structure_index = structure.get("candle_index")

            if structure_index is None:
                continue

            if structure_index <= displacement_index:
                continue

            distance = structure_index - displacement_index

            if distance > self.max_structure_confirmation_window:
                break

            structure_direction = structure.get("direction")

            if structure_direction != direction:
                continue

            return structure

        return None

    def _displacement_score(self, order_block):
        displacement_index = order_block.get(
            "displacement_index"
        )

        created_at_index = order_block.get(
            "created_at_index"
        )

        if (
            displacement_index is None
            or created_at_index is None
        ):
            return 0

        distance = displacement_index - created_at_index

        if distance == 1:
            return 40

        if distance == 2:
            return 30

        if distance == 3:
            return 20

        return 0

    def _structure_score(
        self,
        order_block,
        structure,
    ):
        if structure is None:
            return 0

        displacement_index = order_block.get(
            "displacement_index"
        )

        structure_index = structure.get(
            "candle_index"
        )

        if (
            displacement_index is None
            or structure_index is None
        ):
            return 0

        distance = structure_index - displacement_index

        if distance == 1:
            return 40

        if distance == 2:
            return 30

        if 3 <= distance <= 5:
            return 20

        return 0

    def _context_status(
        self,
        context_score,
        structure,
    ):
        if structure is None:
            return "displacement_confirmed"

        if context_score >= 70:
            return "strong_structural_confirmation"

        if context_score >= self.minimum_context_score:
            return "structurally_confirmed"

        return "weak_structural_confirmation"

    def evaluate_order_block(
        self,
        order_block,
        structure_breaks,
    ):
        result = dict(order_block)

        structure = self._find_structure_confirmation(
            result,
            structure_breaks,
        )

        displacement_score = self._displacement_score(
            result
        )

        structure_score = self._structure_score(
            result,
            structure,
        )

        context_score = (
            displacement_score
            + structure_score
        )

        result["displacement_score"] = displacement_score
        result["structure_score"] = structure_score
        result["context_score"] = context_score

        if structure is not None:
            result["structure_index"] = structure.get(
                "candle_index"
            )
            result["structure_timestamp"] = structure.get(
                "timestamp"
            )
            result["structure_type"] = structure.get(
                "type"
            )
            result["structure_direction"] = structure.get(
                "direction"
            )
        else:
            result["structure_index"] = None
            result["structure_timestamp"] = None
            result["structure_type"] = None
            result["structure_direction"] = None

        result["context_status"] = self._context_status(
            context_score,
            structure,
        )

        result["context_eligible"] = bool(
            result.get("eligible", False)
            and structure is not None
            and context_score >= self.minimum_context_score
        )

        return result

    def evaluate_order_blocks(
        self,
        order_blocks,
        displacement,
        structure_breaks,
    ):
        results = []

        for order_block in order_blocks:
            results.append(
                self.evaluate_order_block(
                    order_block,
                    structure_breaks,
                )
            )

        return results