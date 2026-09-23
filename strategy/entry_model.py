class SMCEntryModel:
    """
    Determines a retracement entry zone from a
    confirmed SMC setup.

    This engine does not place orders.

    The model requires:
        - a valid setup direction
        - a confirmed Order Block
        - optionally, a confirmed FVG

    For long setups:
        entry zone is derived from the bullish OB
        and optionally refined using the bullish FVG.

    For short setups:
        entry zone is derived from the bearish OB
        and optionally refined using the bearish FVG.
    """

    def __init__(
        self,
        use_fvg_refinement=True,
    ):
        self.use_fvg_refinement = (
            use_fvg_refinement
        )

    def _normalize_direction(
        self,
        direction,
    ):
        if direction is None:
            return None

        direction = str(
            direction
        ).lower()

        if direction == "bullish":
            return "long"

        if direction == "bearish":
            return "short"

        if direction in (
            "long",
            "short",
        ):
            return direction

        return None

    def _price(
        self,
        value,
    ):
        try:
            value = float(value)
        except (
            TypeError,
            ValueError,
        ):
            return None

        if value <= 0:
            return None

        return value

    def _get_ob_zone(
        self,
        order_block,
        direction,
    ):
        if not isinstance(
            order_block,
            dict,
        ):
            return None

        if direction == "long":
            low = self._price(
                order_block.get("low")
            )
            high = self._price(
                order_block.get("high")
            )

        elif direction == "short":
            low = self._price(
                order_block.get("low")
            )
            high = self._price(
                order_block.get("high")
            )

        else:
            return None

        if (
            low is None
            or high is None
        ):
            return None

        if high <= low:
            return None

        return {
            "low": low,
            "high": high,
            "source": "order_block",
        }

    def _get_fvg_zone(
        self,
        fvg,
        direction,
    ):
        if not isinstance(
            fvg,
            dict,
        ):
            return None

        fvg_direction = (
            self._normalize_direction(
                fvg.get("direction")
            )
        )

        if (
            fvg_direction != direction
        ):
            return None

        low = self._price(
            fvg.get("gap_low")
        )

        high = self._price(
            fvg.get("gap_high")
        )

        if (
            low is None
            or high is None
        ):
            return None

        if high <= low:
            return None

        return {
            "low": low,
            "high": high,
            "source": "fvg",
        }

    def _refine_zone(
        self,
        order_block_zone,
        fvg_zone,
        direction,
    ):
        if (
            fvg_zone is None
            or not self.use_fvg_refinement
        ):
            return dict(
                order_block_zone
            )

        ob_low = order_block_zone[
            "low"
        ]

        ob_high = order_block_zone[
            "high"
        ]

        fvg_low = fvg_zone[
            "low"
        ]

        fvg_high = fvg_zone[
            "high"
        ]

        overlap_low = max(
            ob_low,
            fvg_low,
        )

        overlap_high = min(
            ob_high,
            fvg_high,
        )

        if overlap_high <= overlap_low:
            return {
                "low": ob_low,
                "high": ob_high,
                "source": "order_block",
            }

        return {
            "low": overlap_low,
            "high": overlap_high,
            "source": "order_block_fvg_overlap",
        }

    def _candidate_entry(
        self,
        zone,
    ):
        low = zone[
            "low"
        ]

        high = zone[
            "high"
        ]

        return (
            low + high
        ) / 2.0

    def generate(
        self,
        setup,
    ):
        if not isinstance(
            setup,
            dict,
        ):
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "invalid_setup",
            }

        if (
            setup.get("setup_status")
            != "valid_setup"
        ):
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "setup_not_valid",
            }

        direction = (
            self._normalize_direction(
                setup.get("direction")
            )
        )

        if direction is None:
            for key in (
                "structure",
                "displacement",
                "order_block",
                "fvg",
            ):
                component = setup.get(
                    key
                )

                if not isinstance(
                    component,
                    dict,
                ):
                    continue

                direction = (
                    self._normalize_direction(
                        component.get(
                            "direction"
                        )
                    )
                )

                if direction is not None:
                    break

        if direction is None:
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "missing_direction",
            }

        order_block = setup.get(
            "order_block"
        )

        order_block_zone = (
            self._get_ob_zone(
                order_block,
                direction,
            )
        )

        if order_block_zone is None:
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "invalid_order_block_zone",
                "direction": direction,
            }

        fvg = setup.get(
            "fvg"
        )

        fvg_zone = (
            self._get_fvg_zone(
                fvg,
                direction,
            )
        )

        entry_zone = self._refine_zone(
            order_block_zone,
            fvg_zone,
            direction,
        )

        candidate_entry = (
            self._candidate_entry(
                entry_zone
            )
        )

        return {
            "approved": True,
            "status": "ENTRY_ZONE_READY",
            "reason": "smc_retracement_zone_ready",
            "direction": direction,
            "entry_zone_low": entry_zone[
                "low"
            ],
            "entry_zone_high": entry_zone[
                "high"
            ],
            "entry_zone_source": entry_zone[
                "source"
            ],
            "candidate_entry": candidate_entry,
            "order_block_low": order_block_zone[
                "low"
            ],
            "order_block_high": order_block_zone[
                "high"
            ],
            "fvg_low": (
                fvg_zone["low"]
                if fvg_zone is not None
                else None
            ),
            "fvg_high": (
                fvg_zone["high"]
                if fvg_zone is not None
                else None
            ),
        }