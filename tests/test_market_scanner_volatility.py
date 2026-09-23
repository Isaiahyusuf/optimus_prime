from market.scanner import MarketScanner


class FakeCandleData:
    def get_klines(
        self,
        symbol,
        interval,
        limit,
    ):
        return [
            {
                "timestamp": index,
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "volume": 1000.0,
            }
            for index in range(limit)
        ]


class FakeSignalEngine:
    def analyze(
        self,
        candles,
    ):
        return {
            "status": "NO_SETUP",
            "reason": "No valid setup.",
            "valid_setups": [],
        }


class FakeVolatilityEngine:
    def analyze(
        self,
        candles,
    ):
        return {
            "status": "VOLATILITY_ANALYZED",
            "atr": 2.0,
            "atr_percent": 2.0,
            "classification": "HIGH",
            "period": 14,
        }


def test_market_scanner_includes_volatility_analysis():
    scanner = MarketScanner(
        symbols=["BTCUSDT"],
        interval="15m",
        candle_limit=50,
        candle_data=FakeCandleData(),
        signal_engine=FakeSignalEngine(),
        volatility_engine=FakeVolatilityEngine(),
    )

    result = scanner.scan_symbol(
        "BTCUSDT"
    )

    assert result["success"] is True

    assert "volatility" in result

    assert result["volatility"] == {
        "status": "VOLATILITY_ANALYZED",
        "atr": 2.0,
        "atr_percent": 2.0,
        "classification": "HIGH",
        "period": 14,
    }


def test_market_scanner_passes_same_candles_to_volatility_engine():
    class RecordingVolatilityEngine:
        def __init__(self):
            self.received_candles = None

        def analyze(
            self,
            candles,
        ):
            self.received_candles = candles

            return {
                "status": "VOLATILITY_ANALYZED",
                "atr": 1.0,
                "atr_percent": 1.0,
                "classification": "NORMAL",
                "period": 14,
            }

    volatility_engine = RecordingVolatilityEngine()

    scanner = MarketScanner(
        symbols=["ETHUSDT"],
        interval="15m",
        candle_limit=20,
        candle_data=FakeCandleData(),
        signal_engine=FakeSignalEngine(),
        volatility_engine=volatility_engine,
    )

    result = scanner.scan_symbol(
        "ETHUSDT"
    )

    assert result["success"] is True
    assert volatility_engine.received_candles == result[
        "candles"
    ]


def test_market_scanner_preserves_signal_result_with_volatility():
    scanner = MarketScanner(
        symbols=["SOLUSDT"],
        interval="15m",
        candle_limit=30,
        candle_data=FakeCandleData(),
        signal_engine=FakeSignalEngine(),
        volatility_engine=FakeVolatilityEngine(),
    )

    result = scanner.scan_symbol(
        "SOLUSDT"
    )

    assert result["status"] == "NO_SETUP"
    assert result["reason"] == "No valid setup."
    assert result["valid_setups"] == []

    assert result[
        "volatility"
    ]["classification"] == "HIGH"
    