class LiquidityTargetSelector:
    """
    Selects a causal external liquidity target.

    Targets must:
    - be confirmed before or at the decision index
    - match the trade direction
    - be external liquidity
    - satisfy the minimum distance requirement
    - satisfy the minimum risk/reward requirement when a stop is supplied
    """

    def __init__(
        self,
        minimum_distance_pct=0.001,
        minimum_risk_reward=2.0,
    ):
        self.minimum_distance_pct = minimum_distance_pct
        self.minimum_risk_reward = minimum_risk_reward

    def _normalize_direction(self, direction):
        if direction is None:
            return None

        direction = str(direction).lower()

        if direction in {"long", "bullish", "buy"}:
            return "long"

        if direction in {"short", "bearish", "sell"}:
            return "short"

        return None

    def _price(self, level):
        price = level.get("price")

        if price is None:
            price = level.get("level")

        if price is None:
            return None

        try:
            return float(price)
        except (TypeError, ValueError):
            return None

    def _decision_index(self, setup):
        decision_index = setup.get("decision_index")

        if decision_index is None:
            decision_index = setup.get("structure_index")

        if decision_index is None:
            return None

        try:
            return int(decision_index)
        except (TypeError, ValueError):
            return None

    def _candidate_is_causal(
        self,
        level,
        decision_index,
    ):
        confirmed_at_index = level.get(
            "confirmed_at_index"
        )

        if confirmed_at_index is None:
            return False

        try:
            confirmed_at_index = int(
                confirmed_at_index
            )
        except (TypeError, ValueError):
            return False

        return confirmed_at_index <= decision_index

    def _candidate_distance_pct(
        self,
        entry_price,
        target_price,
    ):
        if entry_price <= 0:
            return None

        return (
            abs(target_price - entry_price)
            / entry_price
        )

    def _is_external_liquidity(self, level):
        level_type = str(
            level.get("type", "")
        ).lower()

        subtype = str(
            level.get("subtype", "")
        ).lower()

        source = str(
            level.get("source", "")
        ).lower()

        if level_type in {
            "buy_side",
            "sell_side",
        }:
            return True

        if "liquidity" in subtype:
            return True

        if "liquidity" in source:
            return True

        if "swing" in subtype:
            return True

        if "cluster" in subtype:
            return True

        return False

    def _direction_matches(
        self,
        direction,
        level,
    ):
        level_type = str(
            level.get("type", "")
        ).lower()

        if direction == "long":
            return level_type == "buy_side"

        if direction == "short":
            return level_type == "sell_side"

        return False

    def _calculate_risk_reward(
        self,
        direction,
        entry_price,
        stop_loss,
        target_price,
    ):
        risk = abs(
            entry_price - stop_loss
        )

        if risk <= 0:
            return None

        if direction == "long":
            reward = (
                target_price - entry_price
            )
        else:
            reward = (
                entry_price - target_price
            )

        if reward <= 0:
            return None

        return reward / risk

    def select_target(
        self,
        setup,
        liquidity_levels,
        entry_price=None,
        stop_loss=None,
        minimum_risk_reward=None,
    ):
        if not isinstance(setup, dict):
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "invalid_setup",
            }

        direction = self._normalize_direction(
            setup.get("direction")
        )

        if direction is None:
            direction = self._normalize_direction(
                setup.get("setup_direction")
            )

        if direction is None:
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "invalid_direction",
            }

        decision_index = self._decision_index(
            setup
        )

        if decision_index is None:
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "missing_decision_index",
                "direction": direction,
            }

        if entry_price is None:
            entry_price = setup.get(
                "entry_price"
            )

        if entry_price is None:
            entry_price = setup.get(
                "candidate_entry"
            )

        if entry_price is None:
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "missing_entry_price",
                "direction": direction,
                "decision_index": decision_index,
            }

        try:
            entry_price = float(entry_price)
        except (TypeError, ValueError):
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "invalid_entry_price",
                "direction": direction,
                "decision_index": decision_index,
            }

        if entry_price <= 0:
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "invalid_entry_price",
                "direction": direction,
                "decision_index": decision_index,
            }

        if not isinstance(
            liquidity_levels,
            list,
        ):
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "invalid_liquidity_levels",
                "direction": direction,
                "decision_index": decision_index,
                "entry_price": entry_price,
            }

        if minimum_risk_reward is None:
            minimum_risk_reward = (
                self.minimum_risk_reward
            )

        try:
            minimum_risk_reward = float(
                minimum_risk_reward
            )
        except (TypeError, ValueError):
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "invalid_minimum_risk_reward",
                "direction": direction,
                "decision_index": decision_index,
                "entry_price": entry_price,
            }

        if minimum_risk_reward <= 0:
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": "invalid_minimum_risk_reward",
                "direction": direction,
                "decision_index": decision_index,
                "entry_price": entry_price,
            }

        stop_price = None

        if stop_loss is not None:
            try:
                stop_price = float(stop_loss)
            except (TypeError, ValueError):
                return {
                    "approved": False,
                    "status": "NO_TRADE",
                    "reason": "invalid_stop_loss",
                    "direction": direction,
                    "decision_index": decision_index,
                    "entry_price": entry_price,
                }

        candidates = []

        for level in liquidity_levels:
            if not isinstance(level, dict):
                continue

            if not self._candidate_is_causal(
                level,
                decision_index,
            ):
                continue

            if not self._is_external_liquidity(
                level
            ):
                continue

            if not self._direction_matches(
                direction,
                level,
            ):
                continue

            target_price = self._price(level)

            if target_price is None:
                continue

            if direction == "long":
                if target_price <= entry_price:
                    continue
            else:
                if target_price >= entry_price:
                    continue

            distance_pct = (
                self._candidate_distance_pct(
                    entry_price,
                    target_price,
                )
            )

            if distance_pct is None:
                continue

            if (
                distance_pct
                < self.minimum_distance_pct
            ):
                continue

            risk_reward = None

            if stop_price is not None:
                risk_reward = (
                    self._calculate_risk_reward(
                        direction,
                        entry_price,
                        stop_price,
                        target_price,
                    )
                )

                if risk_reward is None:
                    continue

                if (
                    risk_reward
                    < minimum_risk_reward
                ):
                    continue

            candidates.append(
                {
                    "level": level,
                    "target_price": target_price,
                    "distance": abs(
                        target_price
                        - entry_price
                    ),
                    "distance_pct": distance_pct,
                    "risk_reward": risk_reward,
                }
            )

        if not candidates:
            return {
                "approved": False,
                "status": "NO_TRADE",
                "reason": (
                    "no_qualifying_liquidity_target"
                ),
                "direction": direction,
                "entry_price": entry_price,
                "decision_index": decision_index,
                "minimum_distance_pct": (
                    self.minimum_distance_pct
                ),
                "minimum_risk_reward": (
                    minimum_risk_reward
                ),
            }

        candidates.sort(
            key=lambda candidate: (
                candidate["distance"]
            )
        )

        selected = candidates[0]
        level = selected["level"]

        result = {
            "approved": True,
            "status": "TARGET_READY",
            "reason": (
                "external_liquidity_target_found"
            ),
            "direction": direction,
            "entry_price": entry_price,
            "decision_index": decision_index,
            "target_price": selected[
                "target_price"
            ],
            "target_type": level.get(
                "type"
            ),
            "target_subtype": level.get(
                "subtype"
            ),
            "target_index": level.get(
                "index"
            ),
            "target_confirmed_at_index": level.get(
                "confirmed_at_index"
            ),
            "target_distance": selected[
                "distance"
            ],
            "target_distance_pct": selected[
                "distance_pct"
            ],
            "candidate_count": len(
                candidates
            ),
            "minimum_distance_pct": (
                self.minimum_distance_pct
            ),
            "minimum_risk_reward": (
                minimum_risk_reward
            ),
        }

        if selected["risk_reward"] is not None:
            result["target_risk_reward"] = (
                selected["risk_reward"]
            )

        return result