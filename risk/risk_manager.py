class RiskManager:
    """
    Guardian Risk Engine.

    Handles deterministic risk calculations, position sizing,
    futures exposure limits, and risk/reward validation.

    This module does not place orders.
    """

    def __init__(
        self,
        risk_per_trade=0.01,
        min_risk_reward=2.0,
        max_position_value_pct=100.0,
        max_leverage=10.0,
    ):
        self.risk_per_trade = risk_per_trade
        self.min_risk_reward = min_risk_reward

        # Maximum position notional as a percentage of the
        # account equity before leverage is applied.
        #
        # Example:
        # account = $1,000
        # max_position_value_pct = 100
        # max_leverage = 10
        #
        # Maximum notional = $1,000 * 1.0 * 10
        #                  = $10,000
        self.max_position_value_pct = (
            max_position_value_pct
        )

        self.max_leverage = max_leverage

    def validate_risk_parameters(
        self,
        account_equity,
        entry_price,
        stop_loss,
    ):
        if account_equity <= 0:
            return False, "invalid_account_equity"

        if entry_price <= 0:
            return False, "invalid_entry_price"

        if stop_loss <= 0:
            return False, "invalid_stop_loss"

        if self.risk_per_trade <= 0:
            return False, "invalid_risk_percentage"

        if self.risk_per_trade >= 1:
            return False, "risk_percentage_too_high"

        if self.max_position_value_pct <= 0:
            return False, "invalid_position_value_limit"

        if self.max_leverage <= 0:
            return False, "invalid_max_leverage"

        if entry_price == stop_loss:
            return False, "stop_loss_equals_entry"

        return True, "valid"

    def calculate_risk_amount(
        self,
        account_equity,
    ):
        return (
            account_equity
            * self.risk_per_trade
        )

    def calculate_stop_distance(
        self,
        entry_price,
        stop_loss,
    ):
        return abs(
            entry_price - stop_loss
        )

    def calculate_stop_distance_pct(
        self,
        entry_price,
        stop_loss,
    ):
        if entry_price <= 0:
            return 0.0

        distance = self.calculate_stop_distance(
            entry_price,
            stop_loss,
        )

        return distance / entry_price

    def calculate_position_size(
        self,
        account_equity,
        entry_price,
        stop_loss,
    ):
        valid, reason = (
            self.validate_risk_parameters(
                account_equity,
                entry_price,
                stop_loss,
            )
        )

        if not valid:
            return {
                "valid": False,
                "reason": reason,
                "position_size": 0.0,
                "risk_amount": 0.0,
                "stop_distance": 0.0,
                "stop_distance_pct": 0.0,
            }

        risk_amount = (
            self.calculate_risk_amount(
                account_equity,
            )
        )

        stop_distance = (
            self.calculate_stop_distance(
                entry_price,
                stop_loss,
            )
        )

        stop_distance_pct = (
            self.calculate_stop_distance_pct(
                entry_price,
                stop_loss,
            )
        )

        if stop_distance <= 0:
            return {
                "valid": False,
                "reason": "invalid_stop_distance",
                "position_size": 0.0,
                "risk_amount": risk_amount,
                "stop_distance": stop_distance,
                "stop_distance_pct": stop_distance_pct,
            }

        position_size = (
            risk_amount / stop_distance
        )

        return {
            "valid": True,
            "reason": "valid",
            "position_size": position_size,
            "risk_amount": risk_amount,
            "stop_distance": stop_distance,
            "stop_distance_pct": stop_distance_pct,
        }

    def calculate_position_value(
        self,
        position_size,
        entry_price,
    ):
        if (
            position_size <= 0
            or entry_price <= 0
        ):
            return 0.0

        return (
            position_size
            * entry_price
        )

    def calculate_max_position_value(
        self,
        account_equity,
    ):
        if account_equity <= 0:
            return 0.0

        equity_multiplier = (
            self.max_position_value_pct
            / 100.0
        )

        return (
            account_equity
            * equity_multiplier
            * self.max_leverage
        )

    def calculate_effective_leverage(
        self,
        account_equity,
        position_value,
    ):
        if account_equity <= 0:
            return 0.0

        if position_value <= 0:
            return 0.0

        return (
            position_value
            / account_equity
        )

    def validate_position_value(
        self,
        account_equity,
        position_value,
    ):
        if account_equity <= 0:
            return False, "invalid_account_equity"

        if position_value <= 0:
            return False, "invalid_position_value"

        maximum_position_value = (
            self.calculate_max_position_value(
                account_equity,
            )
        )

        if (
            position_value
            > maximum_position_value
        ):
            return (
                False,
                "position_value_exceeds_exposure_limit",
            )

        effective_leverage = (
            self.calculate_effective_leverage(
                account_equity,
                position_value,
            )
        )

        if (
            effective_leverage
            > self.max_leverage
        ):
            return (
                False,
                "effective_leverage_exceeds_limit",
            )

        return True, "valid"

    def calculate_risk_reward(
        self,
        entry_price,
        stop_loss,
        take_profit,
    ):
        if (
            entry_price <= 0
            or stop_loss <= 0
            or take_profit <= 0
        ):
            return {
                "valid": False,
                "reason": "invalid_price",
                "risk_reward": 0.0,
                "risk_distance": 0.0,
                "reward_distance": 0.0,
            }

        risk_distance = abs(
            entry_price - stop_loss
        )

        reward_distance = abs(
            take_profit - entry_price
        )

        if risk_distance <= 0:
            return {
                "valid": False,
                "reason": "invalid_risk_distance",
                "risk_reward": 0.0,
                "risk_distance": risk_distance,
                "reward_distance": reward_distance,
            }

        risk_reward = (
            reward_distance
            / risk_distance
        )

        return {
            "valid": True,
            "reason": "valid",
            "risk_reward": risk_reward,
            "risk_distance": risk_distance,
            "reward_distance": reward_distance,
        }

    def validate_risk_reward(
        self,
        entry_price,
        stop_loss,
        take_profit,
    ):
        result = self.calculate_risk_reward(
            entry_price,
            stop_loss,
            take_profit,
        )

        if not result["valid"]:
            return result

        if (
            result["risk_reward"]
            < self.min_risk_reward
        ):
            return {
                "valid": False,
                "reason": "risk_reward_too_low",
                "risk_reward": result[
                    "risk_reward"
                ],
                "risk_distance": result[
                    "risk_distance"
                ],
                "reward_distance": result[
                    "reward_distance"
                ],
            }

        return {
            "valid": True,
            "reason": "valid",
            "risk_reward": result[
                "risk_reward"
            ],
            "risk_distance": result[
                "risk_distance"
            ],
            "reward_distance": result[
                "reward_distance"
            ],
        }

    def evaluate_trade_risk(
        self,
        account_equity,
        entry_price,
        stop_loss,
        take_profit,
    ):
        position_result = (
            self.calculate_position_size(
                account_equity,
                entry_price,
                stop_loss,
            )
        )

        if not position_result["valid"]:
            return {
                "approved": False,
                "reason": position_result[
                    "reason"
                ],
                "position_size": 0.0,
                "position_value": 0.0,
                "risk_amount": position_result[
                    "risk_amount"
                ],
                "stop_distance": position_result[
                    "stop_distance"
                ],
                "stop_distance_pct": position_result[
                    "stop_distance_pct"
                ],
                "risk_reward": 0.0,
                "effective_leverage": 0.0,
                "maximum_position_value": 0.0,
                "max_leverage": self.max_leverage,
            }

        position_size = (
            position_result["position_size"]
        )

        position_value = (
            self.calculate_position_value(
                position_size,
                entry_price,
            )
        )

        effective_leverage = (
            self.calculate_effective_leverage(
                account_equity,
                position_value,
            )
        )

        maximum_position_value = (
            self.calculate_max_position_value(
                account_equity,
            )
        )

        risk_reward_result = (
            self.validate_risk_reward(
                entry_price,
                stop_loss,
                take_profit,
            )
        )

        risk_reward = risk_reward_result.get(
            "risk_reward",
            0.0,
        )

        if not risk_reward_result["valid"]:
            return {
                "approved": False,
                "reason": risk_reward_result[
                    "reason"
                ],
                "position_size": position_size,
                "position_value": position_value,
                "risk_amount": position_result[
                    "risk_amount"
                ],
                "stop_distance": position_result[
                    "stop_distance"
                ],
                "stop_distance_pct": position_result[
                    "stop_distance_pct"
                ],
                "risk_reward": risk_reward,
                "effective_leverage": effective_leverage,
                "maximum_position_value": maximum_position_value,
                "max_leverage": self.max_leverage,
            }

        position_value_valid, position_reason = (
            self.validate_position_value(
                account_equity,
                position_value,
            )
        )

        if not position_value_valid:
            return {
                "approved": False,
                "reason": position_reason,
                "position_size": position_size,
                "position_value": position_value,
                "risk_amount": position_result[
                    "risk_amount"
                ],
                "stop_distance": position_result[
                    "stop_distance"
                ],
                "stop_distance_pct": position_result[
                    "stop_distance_pct"
                ],
                "risk_reward": risk_reward,
                "effective_leverage": effective_leverage,
                "maximum_position_value": maximum_position_value,
                "max_leverage": self.max_leverage,
            }

        return {
            "approved": True,
            "reason": "risk_approved",
            "position_size": position_size,
            "position_value": position_value,
            "risk_amount": position_result[
                "risk_amount"
            ],
            "stop_distance": position_result[
                "stop_distance"
            ],
            "stop_distance_pct": position_result[
                "stop_distance_pct"
            ],
            "risk_reward": risk_reward,
            "effective_leverage": effective_leverage,
            "maximum_position_value": maximum_position_value,
            "max_leverage": self.max_leverage,
        }