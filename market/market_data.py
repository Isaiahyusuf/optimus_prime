import requests


class MarketData:
    """
    Public market-data client for Bybit.
    No API key is required for these public endpoints.
    """

    BASE_URL = "https://api.bybit.com"

    def get_server_time(self) -> int:
        """
        Get Bybit server time in milliseconds.
        """

        url = f"{self.BASE_URL}/v5/market/time"

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()

        if data["retCode"] != 0:
            raise RuntimeError(
                f"Bybit API error: {data['retMsg']}"
            )

        return int(data["time"])

    def get_ticker(self, symbol: str) -> dict:
        """
        Get the current linear futures ticker
        for one symbol.
        """

        url = f"{self.BASE_URL}/v5/market/tickers"

        params = {
            "category": "linear",
            "symbol": symbol,
        }

        response = requests.get(
            url,
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        if data["retCode"] != 0:
            raise RuntimeError(
                f"Bybit API error: {data['retMsg']}"
            )

        result = data["result"]["list"]

        if not result:
            raise ValueError(
                f"No ticker data found for {symbol}"
            )

        return result[0]

    def get_tickers(self) -> list[dict]:
        """
        Get current linear futures tickers.

        This retrieves the market ticker universe in
        one request instead of requesting each symbol
        individually.

        Returns:
            A list of ticker dictionaries from Bybit.
        """

        url = f"{self.BASE_URL}/v5/market/tickers"

        params = {
            "category": "linear",
        }

        response = requests.get(
            url,
            params=params,
            timeout=10,
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