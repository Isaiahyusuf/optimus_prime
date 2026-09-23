from market.scanner import MarketScanner


class FakeCandleData:
    def get_klines(
        self,
        symbol,
        interval="15m",
        limit=200,
    ):
        return [
            {
                "timestamp": index,
                "open": 100.0 + index,
                "high": 101.0 + index,
                "low": 99.0 + index,
                "close": 100.5 + index,
                "volume": 1000.0,
            }
            for index in range(1, 11)
        ]


class FakeSignalEngine:
    def analyze(self, candles):
        return {
            "status": "NO_SIGNAL",
            "reason": "no_valid_setup",
            "valid_setups": [],
        }


class FakeSymbolConfig:
    def get_symbols(self, exclusions=None):
        return [
            "BTCUSDT",
            "ETHUSDT",
            "SOLUSDT",
        ]


def test_market_scanner_scans_explicit_symbols():
    scanner = MarketScanner(
        symbols=[
            "BTCUSDT",
            "ETHUSDT",
        ],
        candle_data=FakeCandleData(),
        signal_engine=FakeSignalEngine(),
        symbol_config=FakeSymbolConfig(),
    )

    results = scanner.scan()

    assert len(results) == 2

    assert results[0]["symbol"] == "BTCUSDT"
    assert results[1]["symbol"] == "ETHUSDT"

    for result in results:
        assert result["success"] is True
        assert result["status"] == "NO_SIGNAL"
        assert result["reason"] == "no_valid_setup"
        assert result["valid_setups"] == []


def test_market_scanner_automatically_discovers_symbols():
    scanner = MarketScanner(
        symbols=None,
        candle_data=FakeCandleData(),
        signal_engine=FakeSignalEngine(),
        symbol_config=FakeSymbolConfig(),
    )

    symbols = scanner.get_symbols()

    assert symbols == [
        "BTCUSDT",
        "ETHUSDT",
        "SOLUSDT",
    ]


def test_market_scanner_scans_discovered_symbols():
    scanner = MarketScanner(
        symbols=None,
        candle_data=FakeCandleData(),
        signal_engine=FakeSignalEngine(),
        symbol_config=FakeSymbolConfig(),
    )

    results = scanner.scan()

    assert len(results) == 3

    assert [
        result["symbol"]
        for result in results
    ] == [
        "BTCUSDT",
        "ETHUSDT",
        "SOLUSDT",
    ]


def test_market_scanner_returns_valid_setups():
    class SetupSignalEngine:
        def analyze(self, candles):
            return {
                "status": "SIGNALS_FOUND",
                "reason": "valid_setups_found",
                "valid_setups": [
                    {
                        "setup_status": "valid_setup",
                    }
                ],
            }

    scanner = MarketScanner(
        symbols=["BTCUSDT"],
        candle_data=FakeCandleData(),
        signal_engine=SetupSignalEngine(),
    )

    results = scanner.get_valid_setups()

    assert len(results) == 1
    assert results[0]["symbol"] == "BTCUSDT"
    assert len(results[0]["valid_setups"]) == 1


def test_market_scanner_handles_symbol_error():
    class FailingCandleData:
        def get_klines(
            self,
            symbol,
            interval="15m",
            limit=200,
        ):
            raise RuntimeError(
                "test market data failure"
            )

    scanner = MarketScanner(
        symbols=["BTCUSDT"],
        candle_data=FailingCandleData(),
        signal_engine=FakeSignalEngine(),
    )

    results = scanner.scan()

    assert len(results) == 1

    result = results[0]

    assert result["symbol"] == "BTCUSDT"
    assert result["success"] is False
    assert result["status"] == "SCAN_ERROR"
    assert result["valid_setups"] == []
    assert "test market data failure" in result["reason"]


def test_market_scanner_signal_summary():
    scanner = MarketScanner(
        symbols=[
            "BTCUSDT",
            "ETHUSDT",
        ],
        candle_data=FakeCandleData(),
        signal_engine=FakeSignalEngine(),
    )

    summary = scanner.get_signal_summary()

    assert len(summary) == 2

    for item in summary:
        assert "symbol" in item
        assert "success" in item
        assert "status" in item
        assert "reason" in item
        assert "valid_setup_count" in item
        assert item["valid_setup_count"] == 0


def test_market_scanner_passes_exclusions_to_symbol_config():
    class TrackingSymbolConfig:
        def __init__(self):
            self.received_exclusions = None

        def get_symbols(self, exclusions=None):
            self.received_exclusions = exclusions

            return [
                "BTCUSDT",
            ]

    symbol_config = TrackingSymbolConfig()

    scanner = MarketScanner(
        symbols=None,
        candle_data=FakeCandleData(),
        signal_engine=FakeSignalEngine(),
        symbol_config=symbol_config,
        exclusions=[
            "ETHUSDT",
        ],
    )

    symbols = scanner.get_symbols()

    assert symbols == ["BTCUSDT"]
    assert symbol_config.received_exclusions == [
        "ETHUSDT",
    ]