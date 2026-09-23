from risk.protection import ProtectionEngine
from risk.protection_levels import ProtectionLevelEngine
from risk.risk_manager import RiskManager
from strategy.entry_model import SMCEntryModel
from strategy.target_selector import LiquidityTargetSelector


class GuardianTradePlanEngine:
    """
    Guardian Trade Plan Engine.

    Combines the deterministic entry, protection, target,
    and risk engines into one complete trade-plan decision.

    This engine does not place orders.

    Pipeline:

        SMC setup
            ↓
        Entry Model
            ↓
        Structural Stop
            ↓
        Liquidity Target
            ↓
        Protection Validation
            ↓
        Risk Manager
            ↓
        Final Guardian Decision
    """

    def __init__(
        self,
        minimum_risk_reward=2.0,
        stop_buffer_pct=0.0005,
        minimum_target_distance_pct=0.001,
        risk_per_trade=0.01,
        max_position_value_pct=100.0,
        max_leverage=10.0,
    ):
        self.minimum_risk_reward = minimum_risk_reward

        self.entry_engine = SMCEntryModel(
            use_fvg_refinement=True,
        )

        self.protection_level_engine = ProtectionLevelEngine(
            minimum_risk_reward=minimum_risk_reward,
            stop_buffer_pct=stop_buffer_pct,
        )

        self.target_selector = LiquidityTargetSelector(
            minimum_distance_pct=minimum_target_distance_pct,
            minimum_risk_reward=minimum_risk_reward,
        )

        self.protection_engine = ProtectionEngine()

        self.risk_manager = RiskManager(
            risk_per_trade=risk_per_trade,
            min_risk_reward=minimum_risk_reward,
            max_position_value_pct=max_position_value_pct,
            max_leverage=max_leverage,
        )

    def _reject(self, reason, stage, details=None):
        """
        Build a deterministic Guardian rejection result.
        """

        result = {
            "approved": False,
            "status": "NO_TRADE",
            "reason": reason,
            "failed_stage": stage,
        }

        if details is not None:
            result["details"] = details

        return result

    def generate(
        self,
        setup,
        liquidity_levels,
        account_equity,
    ):
        """
        Generate a complete Guardian trade plan.

        Returns an approved trade plan only when every required
        deterministic stage passes.
        """

        if not isinstance(setup, dict):
            return self._reject(
                "invalid_setup",
                "setup",
            )

        if not isinstance(liquidity_levels, list):
            return self._reject(
                "invalid_liquidity_levels",
                "target_selection",
            )

        if account_equity <= 0:
            return self._reject(
                "invalid_account_equity",
                "risk_management",
            )

        if setup.get("setup_status") != "valid_setup":
            return self._reject(
                "setup_not_valid",
                "setup",
            )

        # --------------------------------------------------
        # STEP 1: ENTRY
        # --------------------------------------------------

        entry_result = self.entry_engine.generate(setup)

        if not entry_result.get("approved", False):
            return self._reject(
                entry_result.get(
                    "reason",
                    "entry_rejected",
                ),
                "entry",
                entry_result,
            )

        candidate_entry = entry_result.get(
            "candidate_entry"
        )

        if candidate_entry is None:
            return self._reject(
                "missing_candidate_entry",
                "entry",
                entry_result,
            )

        # --------------------------------------------------
        # STEP 2: STRUCTURAL STOP
        # --------------------------------------------------

        stop_result = (
            self.protection_level_engine.calculate_structural_stop(
                setup,
                entry_price=candidate_entry,
            )
        )

        if not stop_result.get("approved", False):
            return self._reject(
                stop_result.get(
                    "reason",
                    "structural_stop_rejected",
                ),
                "structural_stop",
                stop_result,
            )

        stop_loss = stop_result.get(
            "stop_loss"
        )

        if stop_loss is None:
            return self._reject(
                "missing_stop_loss",
                "structural_stop",
                stop_result,
            )

        # --------------------------------------------------
        # STEP 3: LIQUIDITY TARGET
        # --------------------------------------------------

        target_result = self.target_selector.select_target(
            setup,
            liquidity_levels,
            entry_price=candidate_entry,
            stop_loss=stop_loss,
            minimum_risk_reward=self.minimum_risk_reward,
        )

        if not target_result.get("approved", False):
            return self._reject(
                target_result.get(
                    "reason",
                    "target_rejected",
                ),
                "target_selection",
                target_result,
            )

        take_profit = target_result.get(
            "target_price"
        )

        if take_profit is None:
            return self._reject(
                "missing_take_profit",
                "target_selection",
                target_result,
            )

        # --------------------------------------------------
        # STEP 4: BUILD PROTECTION SETUP
        # --------------------------------------------------

        protection_setup = dict(setup)

        protection_setup["entry_price"] = candidate_entry

        protection_setup["target_liquidity"] = {
            "price": take_profit,
            "type": target_result.get(
                "target_type"
            ),
            "subtype": target_result.get(
                "target_subtype"
            ),
            "index": target_result.get(
                "target_index"
            ),
            "confirmed_at_index": target_result.get(
                "target_confirmed_at_index"
            ),
        }

        protection_result = (
            self.protection_level_engine.generate(
                protection_setup,
                entry_price=candidate_entry,
            )
        )

        if not protection_result.get(
            "approved",
            False,
        ):
            return self._reject(
                protection_result.get(
                    "reason",
                    "protection_levels_rejected",
                ),
                "protection_levels",
                protection_result,
            )

        # --------------------------------------------------
        # STEP 5: PROTECTION VALIDATION
        # --------------------------------------------------

        direction = protection_result.get(
            "direction"
        )

        if direction is None:
            return self._reject(
                "missing_direction",
                "protection_validation",
                protection_result,
            )

        protection_validation = (
            self.protection_engine.evaluate(
                direction=direction,
                entry_price=candidate_entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
        )

        if not protection_validation.get(
            "approved",
            False,
        ):
            return self._reject(
                protection_validation.get(
                    "reason",
                    "protection_validation_rejected",
                ),
                "protection_validation",
                protection_validation,
            )

        # --------------------------------------------------
        # STEP 6: RISK MANAGEMENT
        # --------------------------------------------------

        risk_result = (
            self.risk_manager.evaluate_trade_risk(
                account_equity=account_equity,
                entry_price=candidate_entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
        )

        if not risk_result.get(
            "approved",
            False,
        ):
            return self._reject(
                risk_result.get(
                    "reason",
                    "risk_rejected",
                ),
                "risk_management",
                risk_result,
            )

        # --------------------------------------------------
        # STEP 7: FINAL GUARDIAN PLAN
        # --------------------------------------------------

        return {
            "approved": True,
            "status": "GUARDIAN_APPROVED",
            "reason": "guardian_trade_plan_approved",
            "direction": direction,
            "entry_price": candidate_entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "target_source": protection_result.get(
                "target_source"
            ),
            "risk_distance": protection_result.get(
                "risk_distance"
            ),
            "reward_distance": protection_result.get(
                "reward_distance"
            ),
            "risk_reward": protection_result.get(
                "risk_reward"
            ),
            "risk_amount": risk_result.get(
                "risk_amount"
            ),
            "position_size": risk_result.get(
                "position_size"
            ),
            "position_value": risk_result.get(
                "position_value"
            ),
            "maximum_position_value": risk_result.get(
                "maximum_position_value"
            ),
            "effective_leverage": risk_result.get(
                "effective_leverage"
            ),
            "max_leverage": risk_result.get(
                "max_leverage"
            ),
            "entry": entry_result,
            "stop": stop_result,
            "target": target_result,
            "protection": protection_result,
            "protection_validation": protection_validation,
            "risk": risk_result,
        }