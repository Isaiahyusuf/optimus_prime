class StructureConfirmationEngine:
    """
    Connects displacement with subsequent MSS/BOS events.

    This engine does NOT generate trade signals.

    It confirms whether displacement is followed by
    a nearby structural break in the same direction.
    """

    def __init__(
        self,
        confirmation_window: int = 5,
    ):
        if confirmation_window < 1:
            raise ValueError(
                "confirmation_window must be at least 1."
            )

        self.confirmation_window = confirmation_window

    def match_displacement_to_structure(
        self,
        displacement: list[dict],
        structure_breaks: list[dict],
    ) -> list[dict]:
        """
        Match displacement events with subsequent
        MSS/BOS events.

        Rules:

        1. Structure break must happen after displacement.
        2. Structure break must happen within the
           confirmation window.
        3. Direction must match.
        4. Each structure break can only be used once.
        5. The first valid structure break is selected.
        """

        if not displacement or not structure_breaks:
            return []

        confirmations = []

        used_structure_indices = set()

        ordered_displacement = sorted(
            displacement,
            key=lambda item: item["candle_index"],
        )

        ordered_structure = sorted(
            structure_breaks,
            key=lambda item: item["candle_index"],
        )

        for move in ordered_displacement:

            displacement_index = move[
                "candle_index"
            ]

            expected_direction = move[
                "direction"
            ]

            candidates = []

            for event in ordered_structure:

                structure_index = event[
                    "candle_index"
                ]

                # Structure break must happen after
                # displacement.
                if structure_index <= displacement_index:
                    continue

                # Structure break must be within
                # confirmation window.
                if (
                    structure_index
                    > displacement_index
                    + self.confirmation_window
                ):
                    break

                # Do not reuse the same structural break.
                if structure_index in used_structure_indices:
                    continue

                # Direction must match.
                if (
                    event["direction"]
                    != expected_direction
                ):
                    continue

                candidates.append(event)

            if not candidates:
                continue

            # First valid structural break.
            first = candidates[0]

            structure_index = first[
                "candle_index"
            ]

            used_structure_indices.add(
                structure_index
            )

            confirmations.append(
                {
                    "type": (
                        "displacement_structure_confirmation"
                    ),
                    "direction": expected_direction,
                    "displacement_candle_index": (
                        displacement_index
                    ),
                    "structure_candle_index": (
                        structure_index
                    ),
                    "candles_between": (
                        structure_index
                        - displacement_index
                    ),
                    "structure_type": first["type"],
                    "displacement_timestamp": (
                        move["timestamp"]
                    ),
                    "structure_timestamp": (
                        first["timestamp"]
                    ),
                    "displacement": move,
                    "structure_break": first,
                }
            )

        return confirmations