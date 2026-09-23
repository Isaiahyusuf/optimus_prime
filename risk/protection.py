class ProtectionEngine:
    """
    Guardian Protection Engine.

    Determines whether an entry, stop loss, and take profit
    are structurally valid for a LONG or SHORT setup.

    This module does not place orders.
    """

    def __init__(
        self,
        minimum_risk_reward=2.0,
        minimum_stop_distance_pct=0.001,
    ):
        self.minimum_risk_reward = minimum_risk_reward
        self.minimum_stop_distance_pct = (
            minimum_stop_distance_pct
        )

    def _validate_prices(
        self,
        entry_price,
        stop_loss,
        take_profit,
    ):
        if entry_price <= 0:
            return False, "invalid_entry_price"

        if stop_loss <= 0:
            return False, "invalid_stop_loss"

        if take_profit <= 0:
            return False, "invalid_take_profit"

        return True, "valid"

    def calculate_risk_distance(
        self,
        entry_price,
        stop_loss,
    ):
        return abs(
            entry_price - stop_loss
        )

    def calculate_reward_distance(
        self,
        entry_price,
        take_profit,
    ):
        return abs(
            take_profit - entry_price
        )

    def calculate_risk_reward(
        self,
        entry_price,
        stop_loss,
        take_profit,
    ):
        risk_distance = (
            self.calculate_risk_distance(
                entry_price,
                stop_loss,
            )
        )

        reward_distance = (
            self.calculate_reward_distance(
                entry_price,
                take_profit,
            )
        )

        if risk_distance <= 0:
            return 0.0

        return (
            reward_distance
            / risk_distance
        )

    def validate_long(
        self,
        entry_price,
        stop_loss,
        take_profit,
    ):
        """
        Validate a LONG protection structure.

        LONG requirements:

        stop_loss < entry_price < take_profit
        """

        valid, reason = self._validate_prices(
            entry_price,
            stop_loss,
            take_profit,
        )

        if not valid:
            return {
                "approved": False,
                "reason": reason,
                "risk_distance": 0.0,
                "reward_distance": 0.0,
                "risk_reward": 0.0,
            }

        if stop_loss >= entry_price:
            return {
                "approved": False,
                "reason": "long_stop_must_be_below_entry",
                "risk_distance": 0.0,
                "reward_distance": 0.0,
                "risk_reward": 0.0,
            }

        if take_profit <= entry_price:
            return {
                "approved": False,
                "reason": "long_take_profit_must_be_above_entry",
                "risk_distance": 0.0,
                "reward_distance": 0.0,
                "risk_reward": 0.0,
            }

        risk_distance = (
            self.calculate_risk_distance(
                entry_price,
                stop_loss,
            )
        )

        reward_distance = (
            self.calculate_reward_distance(
                entry_price,
                take_profit,
            )
        )

        risk_reward = (
            self.calculate_risk_reward(
                entry_price,
                stop_loss,
                take_profit,
            )
        )

        minimum_stop_distance = (
            entry_price
            * self.minimum_stop_distance_pct
        )

        if risk_distance < minimum_stop_distance:
            return {
                "approved": False,
                "reason": "stop_distance_too_small",
                "risk_distance": risk_distance,
                "reward_distance": reward_distance,
                "risk_reward": risk_reward,
            }

        if risk_reward < self.minimum_risk_reward:
            return {
                "approved": False,
                "reason": "risk_reward_too_low",
                "risk_distance": risk_distance,
                "reward_distance": reward_distance,
                "risk_reward": risk_reward,
            }

        return {
            "approved": True,
            "reason": "long_protection_approved",
            "risk_distance": risk_distance,
            "reward_distance": reward_distance,
            "risk_reward": risk_reward,
        }

    def validate_short(
        self,
        entry_price,
        stop_loss,
        take_profit,
    ):
        """
        Validate a SHORT protection structure.

        SHORT requirements:

        take_profit < entry_price < stop_loss
        """

        valid, reason = self._validate_prices(
            entry_price,
            stop_loss,
            take_profit,
        )

        if not valid:
            return {
                "approved": False,
                "reason": reason,
                "risk_distance": 0.0,
                "reward_distance": 0.0,
                "risk_reward": 0.0,
            }

        if stop_loss <= entry_price:
            return {
                "approved": False,
                "reason": "short_stop_must_be_above_entry",
                "risk_distance": 0.0,
                "reward_distance": 0.0,
                "risk_reward": 0.0,
            }

        if take_profit >= entry_price:
            return {
                "approved": False,
                "reason": "short_take_profit_must_be_below_entry",
                "risk_distance": 0.0,
                "reward_distance": 0.0,
                "risk_reward": 0.0,
            }

        risk_distance = (
            self.calculate_risk_distance(
                entry_price,
                stop_loss,
            )
        )

        reward_distance = (
            self.calculate_reward_distance(
                entry_price,
                take_profit,
            )
        )

        risk_reward = (
            self.calculate_risk_reward(
                entry_price,
                stop_loss,
                take_profit,
            )
        )

        minimum_stop_distance = (
            entry_price
            * self.minimum_stop_distance_pct
        )

        if risk_distance < minimum_stop_distance:
            return {
                "approved": False,
                "reason": "stop_distance_too_small",
                "risk_distance": risk_distance,
                "reward_distance": reward_distance,
                "risk_reward": risk_reward,
            }

        if risk_reward < self.minimum_risk_reward:
            return {
                "approved": False,
                "reason": "risk_reward_too_low",
                "risk_distance": risk_distance,
                "reward_distance": reward_distance,
                "risk_reward": risk_reward,
            }

        return {
            "approved": True,
            "reason": "short_protection_approved",
            "risk_distance": risk_distance,
            "reward_distance": reward_distance,
            "risk_reward": risk_reward,
        }

    def evaluate(
        self,
        direction,
        entry_price,
        stop_loss,
        take_profit,
    ):
        """
        Evaluate protection according to trade direction.
        """

        normalized_direction = str(
            direction
        ).lower()

        if normalized_direction == "bullish":
            normalized_direction = "long"

        if normalized_direction == "bearish":
            normalized_direction = "short"

        if normalized_direction == "long":
            result = self.validate_long(
                entry_price,
                stop_loss,
                take_profit,
            )

        elif normalized_direction == "short":
            result = self.validate_short(
                entry_price,
                stop_loss,
                take_profit,
            )

        else:
            return {
                "approved": False,
                "reason": "invalid_direction",
                "risk_distance": 0.0,
                "reward_distance": 0.0,
                "risk_reward": 0.0,
            }

        result["direction"] = (
            normalized_direction
        )

        result["entry_price"] = entry_price
        result["stop_loss"] = stop_loss
        result["take_profit"] = take_profit

        return result