import requests


class CandleData:
    """
    Handles OHLCV candle data from Bybit linear futures.
    """

    BASE_URL = "https://api.bybit.com"

    INTERVALS = {
        "1m": "1",
        "3m": "3",
        "5m": "5",
        "15m": "15",
        "30m": "30",
        "1h": "60",
        "4h": "240",
        "1d": "D",
    }

    def get_klines(
        self,
        symbol: str,
        interval: str = "15m",
        limit: int = 200,
    ) -> list[dict]:
        """
        Get OHLCV candles for a linear futures symbol.

        Returns candles ordered from oldest to newest.
        """

        if interval not in self.INTERVALS:
            raise ValueError(
                f"Unsupported interval: {interval}. "
                f"Use one of: {', '.join(self.INTERVALS.keys())}"
            )

        if not 1 <= limit <= 1000:
            raise ValueError("Limit must be between 1 and 1000.")

        url = f"{self.BASE_URL}/v5/market/kline"

        params = {
            "category": "linear",
            "symbol": symbol.upper(),
            "interval": self.INTERVALS[interval],
            "limit": limit,
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

        raw_candles = data["result"]["list"]

        if not raw_candles:
            raise ValueError(
                f"No candle data found for {symbol}."
            )

        candles = []

        for candle in raw_candles:
            candles.append(
                {
                    "timestamp": int(candle[0]),
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4]),
                    "volume": float(candle[5]),
                    "turnover": float(candle[6]),
                }
            )

        # Bybit returns newest first.
        # Optimus needs oldest -> newest.
        candles.reverse()

        return candles