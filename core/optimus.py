from execution.exchange import BybitExchange
from execution.order_engine import OrderEngine
from execution.position_manager import PositionManager
from execution.trade_executor import TradeExecutor
from market.scanner import MarketScanner
from safety.health_monitor import HealthMonitor
from safety.kill_switch import KillSwitch
from risk.account_equity import AccountEquity
from risk.guardian_trade_plan import GuardianTradePlanEngine


class OptimusPrime:
    """
    Central controller for the Optimus Prime trading system.

    The controller orchestrates system components but does not
    contain exchange-specific parsing or trading logic.
    """

    def __init__(self, exchange=None, guardian=None, scanner=None, health_monitor=None, kill_switch=None):
        self.name = "Optimus Prime"
        self.status = "INITIALIZING"

        self.exchange = exchange or BybitExchange()
        self.account_equity = AccountEquity(self.exchange)
        self.guardian = guardian or GuardianTradePlanEngine()
        self.scanner = scanner or MarketScanner()
        self.health_monitor = health_monitor or HealthMonitor()
        self.kill_switch = kill_switch or KillSwitch()

        self.order_engine = OrderEngine(self.exchange)
        self.position_manager = PositionManager(self.exchange)
        self.trade_executor = TradeExecutor(
            exchange=self.exchange,
            order_engine=self.order_engine,
            position_manager=self.position_manager,
            kill_switch=self.kill_switch,
        )

    def check_system_health(self) -> bool:
        """
        Check exchange connectivity and enforce the execution kill switch.

        This method performs only a read-only health check.
        """
        healthy = self.health_monitor.check_exchange_connectivity(
            self.exchange
        )
        self.health_monitor.enforce_kill_switch(self.kill_switch)
        return healthy

    def get_account_equity(self, coin: str = "USDT") -> float:
        """
        Retrieve validated account-level equity.

        No trading is performed.
        """
        return self.account_equity.get_equity(coin)

    def generate_trade_plans(self, scan_results, coin: str = "USDT"):
        """
        Generate Guardian trade plans from completed market scans.

        This method does not place orders.
        """

        if not isinstance(scan_results, list):
            raise ValueError("Scan results must be a list.")

        account_equity = self.get_account_equity(coin)

        plans = []

        for result in scan_results:
            if not isinstance(result, dict):
                continue

            symbol = result.get("symbol")
            analysis = result.get("analysis")

            if not symbol or not isinstance(analysis, dict):
                continue

            liquidity_levels = analysis.get("liquidity", [])
            valid_setups = result.get("valid_setups", [])

            if not isinstance(valid_setups, list):
                continue

            for setup in valid_setups:
                plan = self.guardian.generate(
                    setup=setup,
                    liquidity_levels=liquidity_levels,
                    account_equity=account_equity,
                )

                plans.append(
                    {
                        "symbol": symbol.upper(),
                        "plan": plan,
                    }
                )

        return plans

    def scan_and_generate_trade_plans(self, coin: str = "USDT"):
        """
        Scan the configured market universe and generate Guardian trade plans.

        This method does not place orders.
        """
        if not self.check_system_health():
            raise RuntimeError(
                "SYSTEM_UNHEALTHY: trade planning blocked."
            )

        scan_results = self.scanner.scan()
        return self.generate_trade_plans(scan_results, coin)

    def execute_trade_plan(self, symbol: str, trade_plan: dict) -> dict:
        """
        Execute one Guardian-approved trade plan through TradeExecutor.

        This method does not perform order logic itself. TradeExecutor
        remains responsible for execution sequencing, position verification,
        and TP/SL protection.
        """
        if not symbol:
            raise ValueError("Symbol is required.")

        if not isinstance(trade_plan, dict):
            raise ValueError("Trade plan must be a dictionary.")

        if trade_plan.get("status") != "GUARDIAN_APPROVED":
            raise ValueError(
                "Only GUARDIAN_APPROVED trade plans can be executed."
            )

        return self.trade_executor.execute_trade(
            symbol,
            trade_plan,
        )

    def start(self):
        self.status = "ONLINE"
        print(f"{self.name} is {self.status}.")

    def shutdown(self):
        self.status = "OFFLINE"
        print(f"{self.name} is {self.status}.")
