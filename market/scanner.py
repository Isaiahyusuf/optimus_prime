from config.symbols import SymbolConfig
from market.candles import CandleData
from market.universe import MarketUniverse
from market.volatility import VolatilityEngine
from strategy.signal_engine import SignalEngine


class MarketScanner:
    """
    Scans multiple Bybit linear futures symbols.

    The scanner is responsible only for:
        - resolving the market universe
        - fetching candle data
        - calculating market volatility context
        - running SignalEngine
        - collecting valid setups

    It does not:
        - place orders
        - calculate position size
        - bypass Guardian
        - modify trading strategy
        - execute trades
    """

    def __init__(
        self,
        symbols=None,
        interval="15m",
        candle_limit=200,
        signal_engine=None,
        candle_data=None,
        symbol_config=None,
        exclusions=None,
        market_universe=None,
        volatility_engine=None,
    ):
        self.symbols = symbols
        self.interval = interval
        self.candle_limit = candle_limit

        self.exclusions = (
            exclusions
            if exclusions is not None
            else []
        )

        self.candle_data = (
            candle_data
            if candle_data is not None
            else CandleData()
        )

        self.signal_engine = (
            signal_engine
            if signal_engine is not None
            else SignalEngine()
        )

        self.symbol_config = (
            symbol_config
            if symbol_config is not None
            else SymbolConfig()
        )

        self.market_universe = (
            market_universe
            if market_universe is not None
            else MarketUniverse(
                symbol_config=self.symbol_config
            )
        )

        self.volatility_engine = (
            volatility_engine
            if volatility_engine is not None
            else VolatilityEngine()
        )

    def get_symbols(self):
        """
        Resolve the symbols that should be scanned.

        Explicit symbols take priority.

        For the real SymbolConfig implementation,
        MarketUniverse selects the highest-liquidity
        crypto perpetual markets.

        Backward-compatible SymbolConfig discovery is
        retained for lightweight test doubles or custom
        configurations that only implement get_symbols().
        """

        if self.symbols is not None:
            return [
                symbol.upper()
                for symbol in self.symbols
            ]

        if not hasattr(
            self.symbol_config,
            "get_instruments",
        ):
            return self.symbol_config.get_symbols(
                exclusions=self.exclusions
            )

        markets = self.market_universe.select()

        symbols = [
            market["symbol"]
            for market in markets
        ]

        if self.exclusions:
            excluded = {
                symbol.upper()
                for symbol in self.exclusions
            }

            symbols = [
                symbol
                for symbol in symbols
                if symbol.upper()
                not in excluded
            ]

        return symbols

    def scan_symbol(self, symbol):
        """
        Analyze one futures symbol.

        Volatility is calculated as contextual information.

        A volatility-analysis failure does not invalidate
        the underlying market scan because volatility does
        not control signal generation or execution.
        """

        symbol = symbol.upper()

        try:
            candles = self.candle_data.get_klines(
                symbol=symbol,
                interval=self.interval,
                limit=self.candle_limit,
            )

            volatility = None

            try:
                volatility = (
                    self.volatility_engine.analyze(
                        candles
                    )
                )
            except Exception:
                volatility = None

            analysis = self.signal_engine.analyze(
                candles
            )

            return {
                "symbol": symbol,
                "success": True,
                "status": analysis["status"],
                "reason": analysis["reason"],
                "candles": candles,
                "volatility": volatility,
                "analysis": analysis,
                "valid_setups": analysis[
                    "valid_setups"
                ],
            }

        except Exception as exc:
            return {
                "symbol": symbol,
                "success": False,
                "status": "SCAN_ERROR",
                "reason": str(exc),
                "candles": [],
                "volatility": None,
                "analysis": None,
                "valid_setups": [],
            }

    def scan(self):
        """
        Scan every resolved symbol.

        Returns one result per symbol.
        """

        results = []

        for symbol in self.get_symbols():
            result = self.scan_symbol(symbol)
            results.append(result)

        return results

    def get_valid_setups(self):
        """
        Scan all resolved symbols and return only
        symbols containing valid setups.
        """

        results = self.scan()

        valid_results = []

        for result in results:
            if result["valid_setups"]:
                valid_results.append(result)

        return valid_results

    def get_signal_summary(self):
        """
        Return a lightweight summary of the scan.

        This is useful for dashboards, logs, and
        future notification systems.
        """

        results = self.scan()

        summary = []

        for result in results:
            summary.append(
                {
                    "symbol": result["symbol"],
                    "success": result["success"],
                    "status": result["status"],
                    "reason": result["reason"],
                    "valid_setup_count": len(
                        result["valid_setups"]
                    ),
                }
            )

        return summary