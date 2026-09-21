class SMCConfluenceEngine:
    """
    Connects liquidity sweeps with subsequent displacement.

    This engine does NOT generate trade signals.

    It confirms whether a liquidity sweep is followed by
    meaningful displacement in the expected reversal direction.

    Examples:

        BUY-SIDE SWEEP
            -> bearish displacement

        SELL-SIDE SWEEP
            -> bullish displacement

    If opposite displacement happens first, the sweep is
    considered invalid for this confluence sequence.
    """

    def __init__(
        self,
        confirmation_window: int = 8,
    ):
        if confirmation_window < 1:
            raise ValueError(
                "confirmation_window must be at least 1."
            )

        self.confirmation_window = confirmation_window

    def expected_direction(
        self,
        sweep: dict,
    ) -> str:
        """
        The liquidity engine already provides the expected
        reaction direction in sweep['direction'].
        """

        direction = sweep.get("direction")

        if direction not in {"bullish", "bearish"}:
            raise ValueError(
                f"Unknown sweep direction: {direction}"
            )

        return direction

    def match_sweep_to_displacement(
        self,
        sweeps: list[dict],
        displacement: list[dict],
    ) -> list[dict]:
        """
        Match liquidity sweeps with valid subsequent
        displacement.

        Requirements:

        1. Displacement must happen after the sweep.
        2. It must occur within confirmation_window candles.
        3. It must match the expected reaction direction.
        4. An opposite displacement occurring first invalidates
           the confluence.
        """

        if not sweeps or not displacement:
            return []

        confluences = []

        for sweep in sweeps:

            sweep_index = sweep["candle_index"]
            expected = self.expected_direction(sweep)

            candidates = [
                move
                for move in displacement
                if (
                    move["candle_index"] > sweep_index
                    and move["candle_index"]
                    <= sweep_index + self.confirmation_window
                )
            ]

            if not candidates:
                continue

            # Process displacement chronologically.
            candidates.sort(
                key=lambda item: item["candle_index"]
            )

            first_displacement = candidates[0]

            # If the first meaningful displacement is in the
            # wrong direction, this sweep does not qualify.
            if first_displacement["direction"] != expected:
                continue

            confluences.append(
                {
                    "type": "sweep_displacement_confluence",
                    "sweep_type": sweep["type"],
                    "sweep_direction": sweep["direction"],
                    "expected_direction": expected,
                    "displacement_direction": (
                        first_displacement["direction"]
                    ),
                    "sweep_candle_index": sweep_index,
                    "displacement_candle_index": (
                        first_displacement["candle_index"]
                    ),
                    "candles_between": (
                        first_displacement["candle_index"]
                        - sweep_index
                    ),
                    "sweep_timestamp": sweep["timestamp"],
                    "displacement_timestamp": (
                        first_displacement["timestamp"]
                    ),
                    "sweep": sweep,
                    "displacement": first_displacement,
                }
            )

        return confluences