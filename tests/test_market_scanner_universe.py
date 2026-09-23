from market.scanner import MarketScanner


class FakeCandleData:
    def __init__(self):
        self.calls = []

    def get_klines(
        self,
        symbol,
        interval,
        limit,
    ):
        self.calls.append(
            {
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
            }
        )

        return [
            {
                "timestamp": 1,
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1000.0,
            }
        ]


class FakeSignalEngine:
    def analyze(self, candles):
        return {
            "status": "NO_SIGNAL",
            "reason": "No valid setup.",
            "valid_setups": [],
        }


class FakeMarketUniverse:
    def __init__(self, markets):
        self.markets = markets
        self.select_calls = 0

    def select(self):
        self.select_calls += 1
        return self.markets


def build_market(
    symbol,
    turnover,
):
    return {
        "symbol": symbol,
        "turnover24h": turnover,
        "volume24h": 1000.0,
        "openInterestValue": 500.0,
        "lastPrice": 100.0,
        "bid1Price": 99.9,
        "ask1Price": 100.1,
    }


def test_market_scanner_uses_market_universe():
    universe = FakeMarketUniverse(
        [
            build_market(
                "BTCUSDT",
                10_000_000,
            ),
            build_market(
                "ETHUSDT",
                5_000_000,
            ),
        ]
    )

    scanner = MarketScanner(
        symbols=None,
        market_universe=universe,
        candle_data=FakeCandleData(),
        signal_engine=FakeSignalEngine(),
    )

    symbols = scanner.get_symbols()

    assert symbols == [
        "BTCUSDT",
        "ETHUSDT",
    ]

    assert universe.select_calls == 1


def test_market_scanner_scans_markets_selected_by_universe():
    universe = FakeMarketUniverse(
        [
            build_market(
                "BTCUSDT",
                10_000_000,
            ),
            build_market(
                "SOLUSDT",
                2_000_000,
            ),
        ]
    )

    candle_data = FakeCandleData()

    scanner = MarketScanner(
        symbols=None,
        market_universe=universe,
        candle_data=candle_data,
        signal_engine=FakeSignalEngine(),
    )

    results = scanner.scan()

    assert [
        result["symbol"]
        for result in results
    ] == [
        "BTCUSDT",
        "SOLUSDT",
    ]

    assert [
        call["symbol"]
        for call in candle_data.calls
    ] == [
        "BTCUSDT",
        "SOLUSDT",
    ]


def test_market_scanner_does_not_scan_markets_not_selected_by_universe():
    universe = FakeMarketUniverse(
        [
            build_market(
                "BTCUSDT",
                10_000_000,
            ),
        ]
    )

    candle_data = FakeCandleData()

    scanner = MarketScanner(
        symbols=None,
        market_universe=universe,
        candle_data=candle_data,
        signal_engine=FakeSignalEngine(),
    )

    results = scanner.scan()

    assert [
        result["symbol"]
        for result in results
    ] == [
        "BTCUSDT",
    ]

    assert [
        call["symbol"]
        for call in candle_data.calls
    ] == [
        "BTCUSDT",
    ]


def test_market_scanner_applies_exclusions_after_universe_selection():
    universe = FakeMarketUniverse(
        [
            build_market(
                "BTCUSDT",
                10_000_000,
            ),
            build_market(
                "ETHUSDT",
                5_000_000,
            ),
            build_market(
                "SOLUSDT",
                2_000_000,
            ),
        ]
    )

    scanner = MarketScanner(
        symbols=None,
        market_universe=universe,
        candle_data=FakeCandleData(),
        signal_engine=FakeSignalEngine(),
        exclusions=[
            "ETHUSDT",
        ],
    )

    symbols = scanner.get_symbols()

    assert symbols == [
        "BTCUSDT",
        "SOLUSDT",
    ]


def test_market_scanner_explicit_symbols_bypass_market_universe():
    universe = FakeMarketUniverse(
        [
            build_market(
                "BTCUSDT",
                10_000_000,
            ),
        ]
    )

    scanner = MarketScanner(
        symbols=[
            "ETHUSDT",
            "SOLUSDT",
        ],
        market_universe=universe,
        candle_data=FakeCandleData(),
        signal_engine=FakeSignalEngine(),
    )

    symbols = scanner.get_symbols()

    assert symbols == [
        "ETHUSDT",
        "SOLUSDT",
    ]

    assert universe.select_calls == 0