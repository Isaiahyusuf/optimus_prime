from execution.order_state import OrderState
from execution.order_lifecycle import OrderLifecycle
from execution.protection_recovery import ProtectionRecovery
from execution.protection_verifier import ProtectionVerifier
from execution.trade_record import TradeRecord
class TradeExecutor:
    """
    Executes Guardian-approved trade plans.

    This layer coordinates:
    Guardian approval
    -> OrderEngine normalization
    -> Exchange entry submission
    -> Position verification
    -> TP/SL protection
    """

    def __init__(
        self,
        exchange,
        order_engine,
        position_manager,
        kill_switch=None,
        position_safety_monitor=None,
        order_state=None,
        protection_verifier=None,
        protection_recovery=None,
    ):
        self.exchange = exchange
        self.order_engine = order_engine
        self.position_manager = position_manager
        self.kill_switch = kill_switch
        self.position_safety_monitor = position_safety_monitor
        self.last_trade_record = None
        self.order_state = order_state or OrderState()
        self.order_lifecycle = OrderLifecycle(self.order_state)

        if protection_verifier is not None:
            self.protection_verifier = protection_verifier
        elif self.position_manager is not None:
            self.protection_verifier = ProtectionVerifier(
                self.position_manager
            )
        else:
            self.protection_verifier = None

        if protection_recovery is not None:
            self.protection_recovery = protection_recovery
        elif self.position_manager is not None:
            self.protection_recovery = ProtectionRecovery(
                self.position_manager
            )
        else:
            self.protection_recovery = None

    def create_trade_record(
        self,
        symbol: str,
        order_id: str | None = None,
    ) -> TradeRecord:
        """
        Create a lifecycle record for one trade attempt.
        """

        if not symbol:
            raise ValueError("Symbol is required.")

        record = TradeRecord(
            symbol=symbol.upper(),
            order_id=order_id,
        )
        self.last_trade_record = record
        return record

    def prepare_trade(self, symbol: str, trade_plan: dict) -> dict:
        """
        Validate and prepare a Guardian-approved trade plan.

        This method does not submit an order or modify exchange state.
        """

        if not symbol:
            raise ValueError("Symbol is required.")

        if not isinstance(trade_plan, dict):
            raise ValueError("Trade plan must be a dictionary.")

        if trade_plan.get("status") != "GUARDIAN_APPROVED":
            raise ValueError(
                "Only GUARDIAN_APPROVED trade plans can be executed."
            )

        return self.order_engine.prepare_order(
            symbol.upper(),
            trade_plan,
        )

    def ensure_no_existing_position(self, symbol: str) -> None:
        """
        Prevent a new trade from being submitted when an active
        position already exists for the symbol.

        This method is read-only and never modifies exchange state.
        """

        if not symbol:
            raise ValueError("Symbol is required.")

        symbol = symbol.upper()

        if self.position_manager.has_position(symbol):
            raise RuntimeError(
                f"Active position already exists for {symbol}."
            )

    def ensure_no_existing_entry_order(self, symbol: str) -> None:
        """
        Prevent a new entry when an open order already exists
        for the symbol.

        This method is read-only and never cancels or modifies orders.
        """

        if not symbol:
            raise ValueError("Symbol is required.")

        symbol = symbol.upper()

        open_orders = self.exchange.get_open_orders(symbol)

        if not isinstance(open_orders, list):
            raise ValueError("Open orders response must be a list.")

        if open_orders:
            raise RuntimeError(
                f"Open entry order already exists for {symbol}."
            )

    def preflight(self, symbol: str) -> None:
        """
        Run all safety checks required before submitting a new entry.

        This method is read-only and never modifies exchange state.
        """

        if not symbol:
            raise ValueError("Symbol is required.")

        symbol = symbol.upper()

        if self.kill_switch is not None:
            self.kill_switch.check()

        if self.position_safety_monitor is not None:
            safety_result = self.position_safety_monitor.check(
                symbol,
                expected_size=0.0,
            )

            if self.kill_switch is not None:
                self.position_safety_monitor.enforce_kill_switch(
                    self.kill_switch,
                    safety_result,
                )
                self.kill_switch.check()

        self.ensure_no_existing_position(symbol)
        self.ensure_no_existing_entry_order(symbol)

    def submit_entry(self, symbol: str, trade_plan: dict) -> dict:
        """
        Prepare and submit a Guardian-approved entry order.

        This method does not attach TP/SL protection.
        """

        if not symbol:
            raise ValueError("Symbol is required.")

        self.preflight(symbol)

        prepared_order = self.prepare_trade(
            symbol,
            trade_plan,
        )

        return self.exchange.create_order(
            symbol=prepared_order["symbol"],
            side=prepared_order["side"],
            order_type=prepared_order["orderType"],
            qty=prepared_order["qty"],
            price=prepared_order["price"],
        )

    def get_entry_order_state(
        self,
        symbol: str,
        order_id: str,
    ) -> dict:
        """
        Read and interpret the current state of a submitted entry order.

        This method is read-only and never modifies exchange state.
        """

        if not symbol:
            raise ValueError("Symbol is required.")

        if not order_id:
            raise ValueError("Order ID is required.")

        order = self.exchange.get_order(
            symbol.upper(),
            order_id,
        )

        if order is None:
            return {
                "order_id": order_id,
                "raw_status": None,
                "state": "UNKNOWN",
                "order": None,
            }

        lifecycle = self.order_lifecycle.interpret_with_execution(order)

        result = {
            "order_id": order_id,
            "raw_status": order.get("orderStatus"),
            "state": self.order_state.interpret(order),
            "order": order,
        }

        if lifecycle["execution"] is not None:
            result["execution"] = lifecycle["execution"]

        return result

    def verify_position(
        self,
        symbol: str,
        expected_order: dict,
    ) -> dict:
        """
        Verify that the exchange position matches the expected
        filled entry order.

        This method is read-only and never modifies exchange state.
        """

        if not symbol:
            raise ValueError("Symbol is required.")

        if not isinstance(expected_order, dict):
            raise ValueError(
                "Expected order must be a dictionary."
            )

        symbol = symbol.upper()

        expected_side = expected_order.get("side")
        expected_qty = expected_order.get("qty")

        if expected_side not in {"Buy", "Sell"}:
            raise ValueError(
                "Expected order side must be Buy or Sell."
            )

        if expected_qty is None:
            raise ValueError(
                "Expected order quantity is required."
            )

        try:
            expected_size = float(expected_qty)
        except (TypeError, ValueError):
            raise ValueError(
                "Expected order quantity must be numeric."
            )

        if expected_size <= 0:
            raise ValueError(
                "Expected order quantity must be greater than zero."
            )

        return self.position_manager.reconcile_position(
            symbol,
            expected_side=expected_side,
            expected_size=expected_size,
        )

    def apply_protection(
        self,
        symbol: str,
        trade_plan: dict,
        expected_order: dict,
    ) -> dict:
        """
        Attach TP/SL protection only after the expected position
        has been verified on the exchange.
        """

        if not symbol:
            raise ValueError("Symbol is required.")

        if not isinstance(trade_plan, dict):
            raise ValueError(
                "Trade plan must be a dictionary."
            )

        if not isinstance(expected_order, dict):
            raise ValueError(
                "Expected order must be a dictionary."
            )

        symbol = symbol.upper()

        verification = self.verify_position(
            symbol,
            expected_order,
        )

        if verification["status"] != "MATCH":
            raise RuntimeError(
                "Position verification failed: "
                f"{verification['status']}"
            )

        protection = self.order_engine.prepare_protection_orders(
            symbol,
            trade_plan,
        )

        return self.exchange.set_trading_stop(
            symbol=protection["symbol"],
            stop_loss=protection["stopLoss"],
            take_profit=protection["takeProfit"],
            position_idx=protection["positionIdx"],
            tpsl_mode=protection["tpslMode"],
            sl_trigger_by=protection["slTriggerBy"],
            tp_trigger_by=protection["tpTriggerBy"],
        )

    def recover_protection(
        self,
        symbol: str,
        trade_plan: dict,
        expected_order: dict,
    ) -> dict:
        """
        Perform one controlled TP/SL recovery attempt.

        Recovery is allowed only after the position is re-verified.
        This method performs exactly one protection application and
        then verifies the exchange-reported protection.

        It never loops or performs unlimited retries.
        """

        if not symbol:
            raise ValueError("Symbol is required.")

        if not isinstance(trade_plan, dict):
            raise ValueError("Trade plan must be a dictionary.")

        if not isinstance(expected_order, dict):
            raise ValueError("Expected order must be a dictionary.")

        symbol = symbol.upper()

        verification = self.verify_position(
            symbol,
            expected_order,
        )

        if verification["status"] != "MATCH":
            return {
                "symbol": symbol,
                "status": "RECOVERY_FAILED",
                "reason": (
                    "Position verification failed during protection recovery: "
                    f"{verification['status']}"
                ),
                "verification": verification,
            }

        protection = self.order_engine.prepare_protection_orders(
            symbol,
            trade_plan,
        )

        try:
            protection_result = self.exchange.set_trading_stop(
                symbol=protection["symbol"],
                stop_loss=protection["stopLoss"],
                take_profit=protection["takeProfit"],
                position_idx=protection["positionIdx"],
                tpsl_mode=protection["tpslMode"],
                sl_trigger_by=protection["slTriggerBy"],
                tp_trigger_by=protection["tpTriggerBy"],
            )
        except Exception as exc:
            return {
                "symbol": symbol,
                "status": "RECOVERY_FAILED",
                "reason": f"Protection reapplication failed: {exc}",
                "verification": verification,
            }

        protection_verification = self.protection_verifier.verify(
            symbol,
            expected_stop_loss=float(protection["stopLoss"]),
            expected_take_profit=float(protection["takeProfit"]),
        )

        if not protection_verification["safe"]:
            return {
                "symbol": symbol,
                "status": "RECOVERY_FAILED",
                "reason": (
                    "Protection remained unsafe after the recovery attempt: "
                    f"{protection_verification['status']}"
                ),
                "verification": verification,
                "protection": protection_result,
                "protection_verification": protection_verification,
            }

        return {
            "symbol": symbol,
            "status": "PROTECTED",
            "reason": "Protection recovery succeeded.",
            "verification": verification,
            "protection": protection_result,
            "protection_verification": protection_verification,
        }

    def execute_trade(
        self,
        symbol: str,
        trade_plan: dict,
    ) -> dict:
        """
        Execute a complete Guardian-approved trade workflow.

        Workflow:
        1. Submit the entry order.
        2. Verify the resulting exchange position.
        3. Prepare and apply TP/SL protection only after verification succeeds.

        This method does not bypass Guardian approval or recalculate risk.
        """

        if not symbol:
            raise ValueError("Symbol is required.")

        if not isinstance(trade_plan, dict):
            raise ValueError(
                "Trade plan must be a dictionary."
            )

        self.preflight(symbol)

        prepared_order = self.prepare_trade(
            symbol,
            trade_plan,
        )

        trade_record = self.create_trade_record(
            symbol.upper(),
        )

        entry = self.exchange.create_order(
            symbol=prepared_order["symbol"],
            side=prepared_order["side"],
            order_type=prepared_order["orderType"],
            qty=prepared_order["qty"],
            price=prepared_order["price"],
        )

        order_id = entry.get("orderId")

        if order_id:
            trade_record.order_id = order_id
            trade_record.update_state("ENTRY_SUBMITTED")

        if not order_id:
            raise RuntimeError(
                "ENTRY_ORDER_STATE_UNKNOWN: "
                "exchange did not return an order ID."
            )

        order_state = self.get_entry_order_state(
            symbol,
            order_id,
        )

        trade_record.update_state(
            self.order_lifecycle.interpret(
                order_state["order"]
            )
        )

        execution = order_state.get("execution")

        if execution is not None:
            trade_record.update_execution(
                order_quantity=execution["order_quantity"],
                filled_quantity=execution["filled_quantity"],
                remaining_quantity=execution["remaining_quantity"],
                average_fill_price=execution["average_fill_price"],
            )

        if order_state["state"] != "FILLED":
            status_map = {
                "PENDING": "ENTRY_PENDING",
                "PARTIALLY_FILLED": "ENTRY_PARTIALLY_FILLED",
                "CANCELLED": "ENTRY_CANCELLED",
                "REJECTED": "ENTRY_REJECTED",
                "UNKNOWN": "ENTRY_STATE_UNKNOWN",
            }

            if order_state["state"] == "PARTIALLY_FILLED":
                try:
                    self.exchange.cancel_order(
                        symbol.upper(),
                        order_id,
                    )
                except Exception as exc:
                    trade_record.update_state(
                        "ENTRY_CANCELLATION_FAILED"
                    )
                    raise RuntimeError(
                        "Partial entry cancellation failed"
                    ) from exc

            return {
                "symbol": symbol.upper(),
                "entry": entry,
                "order_state": order_state,
                "trade_record": trade_record.snapshot(),
                "status": status_map.get(
                    order_state["state"],
                    "ENTRY_STATE_UNKNOWN",
                ),
            }

        verification = self.verify_position(
            symbol,
            prepared_order,
        )

        if verification["status"] != "MATCH":
            trade_record.update_state(
                "POSITION_VERIFICATION_FAILED"
            )
            raise RuntimeError(
                "Position verification failed: "
                f"{verification['status']}"
            )

        protection = self.order_engine.prepare_protection_orders(
            symbol.upper(),
            trade_plan,
        )

        try:
            protection_result = self.exchange.set_trading_stop(
                symbol=protection["symbol"],
                stop_loss=protection["stopLoss"],
                take_profit=protection["takeProfit"],
                position_idx=protection["positionIdx"],
                tpsl_mode=protection["tpslMode"],
                sl_trigger_by=protection["slTriggerBy"],
                tp_trigger_by=protection["tpTriggerBy"],
            )

            trade_record.update_state("PROTECTION_APPLIED")
        except Exception as exc:
            protection_verification = self.protection_verifier.verify(
                symbol.upper(),
                expected_stop_loss=float(protection["stopLoss"]),
                expected_take_profit=float(protection["takeProfit"]),
            )

            if protection_verification["safe"]:
                trade_record.update_state("PROTECTION_APPLIED")

                return {
                    "symbol": symbol.upper(),
                    "entry": entry,
                    "order_state": order_state,
                    "verification": verification,
                    "protection": None,
                    "protection_verification": protection_verification,
                    "trade_record": trade_record.snapshot(),
                    "status": "PROTECTED",
                }

            trade_record.update_state("PROTECTION_FAILED")

            recovery = self.protection_recovery.evaluate(
                symbol.upper(),
                expected_stop_loss=float(protection["stopLoss"]),
                expected_take_profit=float(protection["takeProfit"]),
            )

            if recovery["action"] == "REAPPLY_PROTECTION":
                recovery_result = self.recover_protection(
                    symbol.upper(),
                    trade_plan,
                    prepared_order,
                )

                if recovery_result["status"] == "PROTECTED":
                    trade_record.update_state("PROTECTION_APPLIED")

                    return {
                        "symbol": symbol.upper(),
                        "entry": entry,
                        "order_state": order_state,
                        "verification": verification,
                        "protection": recovery_result["protection"],
                        "protection_verification": (
                            recovery_result["protection_verification"]
                        ),
                        "recovery": recovery_result,
                        "trade_record": trade_record.snapshot(),
                        "status": "PROTECTED",
                    }

                raise RuntimeError(
                    "POSITION_ACTIVE_UNPROTECTED: "
                    "TP/SL protection remained unsafe after one "
                    "controlled recovery attempt; "
                    f"recovery_status={recovery_result['status']}; "
                    f"recovery_reason={recovery_result['reason']}"
                )

            raise RuntimeError(
                "POSITION_ACTIVE_UNPROTECTED: "
                "protection application raised an exception and "
                "exchange verification remained unsafe: "
                f"{protection_verification['status']}; "
                f"recovery_action={recovery['action']}; "
                f"application_error={exc}"
            ) from exc

        protection_verification = self.protection_verifier.verify(
            symbol.upper(),
            expected_stop_loss=float(protection["stopLoss"]),
            expected_take_profit=float(protection["takeProfit"]),
        )

        if not protection_verification["safe"]:
            trade_record.update_state("PROTECTION_FAILED")

            recovery = self.protection_recovery.evaluate(
                symbol.upper(),
                expected_stop_loss=float(protection["stopLoss"]),
                expected_take_profit=float(protection["takeProfit"]),
            )

            if recovery["action"] == "REAPPLY_PROTECTION":
                recovery_result = self.recover_protection(
                    symbol.upper(),
                    trade_plan,
                    prepared_order,
                )

                if recovery_result["status"] == "PROTECTED":
                    trade_record.update_state("PROTECTION_APPLIED")

                    return {
                        "symbol": symbol.upper(),
                        "entry": entry,
                        "order_state": order_state,
                        "verification": verification,
                        "protection": recovery_result["protection"],
                        "protection_verification": (
                            recovery_result["protection_verification"]
                        ),
                        "recovery": recovery_result,
                        "trade_record": trade_record.snapshot(),
                        "status": "PROTECTED",
                    }

                raise RuntimeError(
                    "POSITION_ACTIVE_UNPROTECTED: "
                    "TP/SL protection remained unsafe after one "
                    "controlled recovery attempt; "
                    f"recovery_status={recovery_result['status']}; "
                    f"recovery_reason={recovery_result['reason']}"
                )

            raise RuntimeError(
                "POSITION_ACTIVE_UNPROTECTED: "
                "TP/SL protection was applied but exchange verification "
                f"failed: {protection_verification['status']}; "
                f"recovery_action={recovery['action']}"
            )

        return {
            "symbol": symbol.upper(),
            "entry": entry,
            "order_state": order_state,
            "verification": verification,
            "protection": protection_result,
            "protection_verification": protection_verification,
            "trade_record": trade_record.snapshot(),
            "status": "PROTECTED",
        }
