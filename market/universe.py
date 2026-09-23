from market.market_data import MarketData
from config.symbols import SymbolConfig


class MarketUniverse:
    """
    Selects liquid Bybit crypto linear perpetual markets.

    Responsibilities:
        - retrieve instrument metadata
        - retrieve live ticker data
        - identify crypto perpetuals
        - filter low-liquidity markets
        - rank markets by 24h turnover
        - return the highest-liquidity candidates

    This class does not:
        - fetch candles
        - generate signals
        - calculate risk
        - place orders
    """

    def __init__(
        self,
        market_data=None,
        symbol_config=None,
        min_turnover_24h=1_000_000.0,
        max_symbols=50,
    ):
        self.market_data = (
            market_data
            if market_data is not None
            else MarketData()
        )

        self.symbol_config = (
            symbol_config
            if symbol_config is not None
            else SymbolConfig()
        )

        if min_turnover_24h < 0:
            raise ValueError(
                "min_turnover_24h cannot be negative."
            )

        if max_symbols < 1:
            raise ValueError(
                "max_symbols must be at least 1."
            )

        self.min_turnover_24h = float(
            min_turnover_24h
        )

        self.max_symbols = int(max_symbols)

    def _parse_float(
        self,
        value,
        default=0.0,
    ):
        """
        Safely convert a ticker value to float.
        """

        try:
            return float(value)
        except (
            TypeError,
            ValueError,
        ):
            return default

    def _is_valid_numeric_value(
        self,
        value,
    ):
        """
        Return True only when value is a valid
        non-negative finite number.
        """

        try:
            number = float(value)
        except (
            TypeError,
            ValueError,
        ):
            return False

        if number != number:
            return False

        if number == float("inf"):
            return False

        if number == float("-inf"):
            return False

        if number < 0:
            return False

        return True

    def get_crypto_instruments(self):
        """
        Return active crypto linear perpetual instruments.

        Bybit uses an empty symbolType for crypto
        linear perpetual instruments, while products
        such as stocks and commodities have explicit
        symbolType values.
        """

        instruments = (
            self.symbol_config.get_instruments()
        )

        crypto_instruments = []

        for instrument in instruments:
            if not isinstance(instrument, dict):
                continue

            if instrument.get("status") != "Trading":
                continue

            if instrument.get("contractType") != (
                "LinearPerpetual"
            ):
                continue

            if instrument.get("settleCoin") != "USDT":
                continue

            symbol_type = instrument.get(
                "symbolType",
                "",
            )

            if symbol_type not in (
                None,
                "",
            ):
                continue

            symbol = instrument.get("symbol")

            if not symbol:
                continue

            crypto_instruments.append(
                instrument
            )

        return crypto_instruments

    def get_crypto_symbols(self):
        """
        Return active crypto linear perpetual symbols.
        """

        return sorted(
            {
                str(
                    instrument["symbol"]
                ).upper()
                for instrument
                in self.get_crypto_instruments()
            }
        )

    def filter_tickers(
        self,
        tickers,
        allowed_symbols=None,
    ):
        """
        Filter ticker data to eligible crypto markets.

        Invalid or malformed ticker records are ignored.
        """

        if not isinstance(tickers, list):
            raise ValueError(
                "tickers must be a list."
            )

        if allowed_symbols is None:
            allowed_symbols = set(
                self.get_crypto_symbols()
            )
        else:
            allowed_symbols = {
                str(symbol).upper()
                for symbol in allowed_symbols
            }

        filtered = []

        for ticker in tickers:
            if not isinstance(ticker, dict):
                continue

            symbol = ticker.get("symbol")

            if not symbol:
                continue

            symbol = str(symbol).upper()

            if symbol not in allowed_symbols:
                continue

            if "turnover24h" not in ticker:
                continue

            turnover = ticker.get(
                "turnover24h"
            )

            if not self._is_valid_numeric_value(
                turnover
            ):
                continue

            turnover = float(turnover)

            if turnover < self.min_turnover_24h:
                continue

            filtered.append(ticker)

        return filtered

    def rank_tickers(
        self,
        tickers,
        allowed_symbols=None,
    ):
        """
        Rank eligible crypto markets by 24h turnover.

        Highest turnover appears first.
        """

        filtered = self.filter_tickers(
            tickers,
            allowed_symbols=allowed_symbols,
        )

        return sorted(
            filtered,
            key=lambda ticker: float(
                ticker["turnover24h"]
            ),
            reverse=True,
        )

    def select(self):
        """
        Retrieve live market data and return the
        highest-liquidity crypto candidates.
        """

        crypto_symbols = set(
            self.get_crypto_symbols()
        )

        tickers = self.market_data.get_tickers()

        ranked = self.rank_tickers(
            tickers,
            allowed_symbols=crypto_symbols,
        )

        selected = ranked[: self.max_symbols]

        return [
            {
                "symbol": str(
                    ticker["symbol"]
                ).upper(),
                "turnover24h": float(
                    ticker["turnover24h"]
                ),
                "volume24h": self._parse_float(
                    ticker.get("volume24h")
                ),
                "openInterestValue": self._parse_float(
                    ticker.get(
                        "openInterestValue"
                    )
                ),
                "lastPrice": self._parse_float(
                    ticker.get("lastPrice")
                ),
                "bid1Price": self._parse_float(
                    ticker.get("bid1Price")
                ),
                "ask1Price": self._parse_float(
                    ticker.get("ask1Price")
                ),
            }
            for ticker in selected
        ]

    def get_symbols(self):
        """
        Return only the selected crypto market symbols.
        """

        return [
            market["symbol"]
            for market in self.select()
        ]