import requests


class SymbolConfig:
    """
    Handles the Optimus Prime futures symbol universe.

    This module is responsible for discovering and
    filtering Bybit linear USDT perpetual symbols.

    It does not:
        - analyze markets
        - generate trading signals
        - calculate risk
        - place orders
    """

    BASE_URL = "https://api.bybit.com"

    def __init__(
        self,
        base_url=None,
        timeout=10,
    ):
        self.base_url = (
            base_url
            if base_url is not None
            else self.BASE_URL
        )

        self.timeout = timeout

    def get_instruments(self):
        """
        Retrieve active Bybit linear futures instruments.

        Returns the complete instrument metadata returned
        by Bybit.
        """

        url = (
            f"{self.base_url}"
            "/v5/market/instruments-info"
        )

        params = {
            "category": "linear",
            "settleCoin": "USDT",
            "limit": 1000,
        }

        response = requests.get(
            url,
            params=params,
            timeout=self.timeout,
        )

        response.raise_for_status()

        data = response.json()

        if data["retCode"] != 0:
            raise RuntimeError(
                f"Bybit API error: {data['retMsg']}"
            )

        return (
            data.get("result", {})
            .get("list", [])
        )

    def get_linear_symbols(self):
        """
        Retrieve active USDT-settled linear perpetual
        futures symbols from Bybit.

        Returns symbols in uppercase.
        """

        instruments = self.get_instruments()

        symbols = []

        for instrument in instruments:
            if instrument.get("status") != "Trading":
                continue

            if instrument.get("contractType") != (
                "LinearPerpetual"
            ):
                continue

            symbol = instrument.get("symbol")

            if not symbol:
                continue

            symbols.append(symbol.upper())

        return sorted(set(symbols))

    def get_symbols(
        self,
        exclusions=None,
    ):
        """
        Return the configured futures universe.

        Optional exclusions can remove specific symbols.
        """

        symbols = self.get_linear_symbols()

        if exclusions is None:
            exclusions = []

        excluded = {
            symbol.upper()
            for symbol in exclusions
        }

        return [
            symbol
            for symbol in symbols
            if symbol not in excluded
        ]