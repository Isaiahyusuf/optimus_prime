class ProtectionLevelEngine:
    """
    Guardian SMC Protection Level Engine.

    Generates and validates structural stop-loss and
    take-profit levels from an SMC setup.

    This engine does not place orders.
    """

    def __init__(
        self,
        minimum_risk_reward=2.0,
        stop_buffer_pct=0.0005,
    ):
        self.minimum_risk_reward = minimum_risk_reward
        self.stop_buffer_pct = stop_buffer_pct

    def _normalize_direction(self, direction):
        if direction is None:
            return None

        direction = str(direction).lower()

        if direction == "bullish":
            return "long"

        if direction == "bearish":
            return "short"

        if direction in ("long", "short"):
            return direction

        return None

    def _get_price(
        self,
        item,
        keys,
    ):
        if not isinstance(item, dict):
            return None

        for key in keys:
            value = item.get(key)

            if value is None:
                continue

            try:
                value = float(value)
            except (TypeError, ValueError):
                continue

            if value > 0:
                return value

        return None

    def _get_setup_direction(self, setup):
        direction = setup.get("direction")

        if direction is not None:
            return self._normalize_direction(
                direction
            )

        for key in (
            "structure",
            "sweep",
            "displacement",
            "order_block",
            "fvg",
        ):
            component = setup.get(key)

            if not isinstance(component, dict):
                continue

            direction = component.get(
                "direction"
            )

            normalized = self._normalize_direction(
                direction
            )

            if normalized is not None:
                return normalized

        return None

    def _get_entry_price(
        self,
        setup,
        entry_price=None,
    ):
        if entry_price is not None:
            try:
                entry_price = float(entry_price)

                if entry_price > 0:
                    return entry_price
            except (TypeError, ValueError):
                pass

        for key in (
            "entry_price",
            "entry",
        ):
            price = self._get_price(
                setup,
                (key,),
            )

            if price is not None:
                return price

        return None

    def _get_structure_price(
        self,
        setup,
    ):
        structure = setup.get("structure")

        return self._get_price(
            structure,
            (
                "price",
                "level",
                "break_price",
                "close",
            ),
        )

    def _get_order_block_boundary(
        self,
        setup,
        direction,
    ):
        order_block = setup.get(
            "order_block"
        )

        if not isinstance(order_block, dict):
            return None

        if direction == "long":
            return self._get_price(
                order_block,
                (
                    "low",
                    "bottom",
                    "zone_low",
                    "price_low",
                ),
            )

        return self._get_price(
            order_block,
            (
                "high",
                "top",
                "zone_high",
                "price_high",
            ),
        )

    def _get_fvg_target(
        self,
        setup,
        direction,
    ):
        fvg = setup.get("fvg")

        if not isinstance(fvg, dict):
            return None

        if direction == "long":
            return self._get_price(
                fvg,
                (
                    "gap_high",
                    "high",
                    "top",
                ),
            )

        return self._get_price(
            fvg,
            (
                "gap_low",
                "low",
                "bottom",
            ),
        )

    def _get_liquidity_target(
        self,
        setup,
        direction,
    ):
        """
        Extract the explicitly selected liquidity target.

        This engine does not search for or invent liquidity.
        The target selector is responsible for selecting
        the causal external liquidity target.
        """

        for key in (
            "target_liquidity",
            "liquidity_target",
            "target",
        ):
            target = setup.get(key)

            price = self._get_price(
                target,
                (
                    "price",
                    "level",
                    "target_price",
                ),
            )

            if price is not None:
                return price

            if isinstance(target, (int, float)):
                if target > 0:
                    return float(target)

        liquidity = setup.get(
            "liquidity"
        )

        if isinstance(liquidity, dict):
            price = self._get_price(
                liquidity,
                (
                    "price",
                    "level",
                    "target_price",
                ),
            )

            if price is not None:
                return price

        return None

    def _calculate_stop(
        self,
        entry_price,
        direction,
        order_block_boundary,
        structure_price,
    ):
        candidates = []

        if direction == "long":
            if (
                order_block_boundary is not None
                and order_block_boundary < entry_price
            ):
                candidates.append(
                    order_block_boundary
                )

            if (
                structure_price is not None
                and structure_price < entry_price
            ):
                candidates.append(
                    structure_price
                )

            if not candidates:
                return None

            structural_stop = min(candidates)

            buffer = (
                entry_price
                * self.stop_buffer_pct
            )

            return structural_stop - buffer

        if direction == "short":
            if (
                order_block_boundary is not None
                and order_block_boundary > entry_price
            ):
                candidates.append(
                    order_block_boundary
                )

            if (
                structure_price is not None
                and structure_price > entry_price
            ):
                candidates.append(
                    structure_price
                )

            if not candidates:
                return None

            structural_stop = max(candidates)

            buffer = (
                entry_price
                * self.stop_buffer_pct
            )

            return structural_stop + buffer

        return None

    def calculate_structural_stop(
        self,
        setup,
        entry_price=None,
    ):
        """
        Calculate the structural stop without requiring
        a take-profit target.

        This is used by the target selector so that target
        selection can evaluate risk/reward without duplicating
        Guardian's stop calculation logic.
        """

        if not isinstance(setup, dict):
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "invalid_setup",
            }

        direction = self._get_setup_direction(
            setup
        )

        if direction is None:
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "missing_direction",
            }

        entry = self._get_entry_price(
            setup,
            entry_price,
        )

        if entry is None:
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "missing_entry_price",
                "direction": direction,
            }

        structure_price = (
            self._get_structure_price(
                setup
            )
        )

        order_block_boundary = (
            self._get_order_block_boundary(
                setup,
                direction,
            )
        )

        stop_loss = self._calculate_stop(
            entry,
            direction,
            order_block_boundary,
            structure_price,
        )

        if stop_loss is None:
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "no_structural_stop_available",
                "direction": direction,
                "entry_price": entry,
            }

        if direction == "long" and stop_loss >= entry:
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "invalid_long_stop",
                "direction": direction,
                "entry_price": entry,
                "stop_loss": stop_loss,
            }

        if direction == "short" and stop_loss <= entry:
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "invalid_short_stop",
                "direction": direction,
                "entry_price": entry,
                "stop_loss": stop_loss,
            }

        return {
            "approved": True,
            "status": "STRUCTURAL_STOP_READY",
            "reason": "structural_stop_calculated",
            "direction": direction,
            "entry_price": entry,
            "stop_loss": stop_loss,
            "risk_distance": abs(
                entry - stop_loss
            ),
        }

    def _calculate_target(
        self,
        entry_price,
        direction,
        liquidity_target,
        fvg_target,
    ):
        """
        Select the take-profit target.

        Priority:

        1. Explicit external liquidity target selected
           by LiquidityTargetSelector.
        2. FVG target as fallback only when no valid
           liquidity target is available.
        """

        if direction == "long":
            if (
                liquidity_target is not None
                and liquidity_target > entry_price
            ):
                return (
                    liquidity_target,
                    "external_liquidity",
                )

            if (
                fvg_target is not None
                and fvg_target > entry_price
            ):
                return (
                    fvg_target,
                    "fvg_fallback",
                )

            return None, None

        if direction == "short":
            if (
                liquidity_target is not None
                and liquidity_target < entry_price
            ):
                return (
                    liquidity_target,
                    "external_liquidity",
                )

            if (
                fvg_target is not None
                and fvg_target < entry_price
            ):
                return (
                    fvg_target,
                    "fvg_fallback",
                )

            return None, None

        return None, None

    def calculate_risk_reward(
        self,
        entry_price,
        stop_loss,
        take_profit,
    ):
        risk_distance = abs(
            entry_price - stop_loss
        )

        reward_distance = abs(
            take_profit - entry_price
        )

        if risk_distance <= 0:
            return 0.0

        return (
            reward_distance
            / risk_distance
        )

    def generate(
        self,
        setup,
        entry_price=None,
    ):
        if not isinstance(setup, dict):
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "invalid_setup",
            }

        direction = self._get_setup_direction(
            setup
        )

        if direction is None:
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "missing_direction",
            }

        entry = self._get_entry_price(
            setup,
            entry_price,
        )

        if entry is None:
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "missing_entry_price",
                "direction": direction,
            }

        stop_result = (
            self.calculate_structural_stop(
                setup,
                entry_price=entry,
            )
        )

        if not stop_result.get(
            "approved"
        ):
            return stop_result

        stop_loss = stop_result.get(
            "stop_loss"
        )

        liquidity_target = (
            self._get_liquidity_target(
                setup,
                direction,
            )
        )

        fvg_target = (
            self._get_fvg_target(
                setup,
                direction,
            )
        )

        take_profit, target_source = (
            self._calculate_target(
                entry,
                direction,
                liquidity_target,
                fvg_target,
            )
        )

        if take_profit is None:
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "no_valid_target_available",
                "direction": direction,
                "entry_price": entry,
                "stop_loss": stop_loss,
            }

        if direction == "long":
            if take_profit <= entry:
                return {
                    "approved": False,
                    "status": "NO_TRADE",
                    "reason": "invalid_long_target",
                    "direction": direction,
                    "entry_price": entry,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "target_source": target_source,
                }

        if direction == "short":
            if take_profit >= entry:
                return {
                    "approved": False,
                    "status": "NO_TRADE",
                    "reason": "invalid_short_target",
                    "direction": direction,
                    "entry_price": entry,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "target_source": target_source,
                }

        risk_distance = abs(
            entry - stop_loss
        )

        reward_distance = abs(
            take_profit - entry
        )

        risk_reward = (
            self.calculate_risk_reward(
                entry,
                stop_loss,
                take_profit,
            )
        )

        if risk_reward < self.minimum_risk_reward:
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "risk_reward_too_low",
                "direction": direction,
                "entry_price": entry,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "target_source": target_source,
                "risk_distance": risk_distance,
                "reward_distance": reward_distance,
                "risk_reward": risk_reward,
            }

        return {
            "approved": True,
            "status": "PROTECTION_APPROVED",
            "reason": "structural_protection_valid",
            "direction": direction,
            "entry_price": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "target_source": target_source,
            "risk_distance": risk_distance,
            "reward_distance": reward_distance,
            "risk_reward": risk_reward,
        }