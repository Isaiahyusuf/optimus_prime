from market.universe import MarketUniverse


class FakeMarketData:
    def __init__(self, tickers):
        self.tickers = tickers
        self.get_tickers_calls = 0

    def get_tickers(self):
        self.get_tickers_calls += 1
        return self.tickers


class FakeSymbolConfig:
    def __init__(self, instruments):
        self.instruments = instruments
        self.get_instruments_calls = 0

    def get_instruments(self):
        self.get_instruments_calls += 1
        return self.instruments


def build_crypto_instrument(symbol):
    return {
        "symbol": symbol,
        "contractType": "LinearPerpetual",
        "status": "Trading",
        "settleCoin": "USDT",
        "symbolType": "",
    }


def build_stock_instrument(symbol):
    return {
        "symbol": symbol,
        "contractType": "LinearPerpetual",
        "status": "Trading",
        "settleCoin": "USDT",
        "symbolType": "stock",
    }


def build_commodity_instrument(symbol):
    return {
        "symbol": symbol,
        "contractType": "LinearPerpetual",
        "status": "Trading",
        "settleCoin": "USDT",
        "symbolType": "commodity",
    }


def build_ticker(
    symbol,
    turnover,
    volume=1000.0,
    open_interest=500.0,
    last_price=100.0,
    bid_price=99.9,
    ask_price=100.1,
):
    return {
        "symbol": symbol,
        "turnover24h": str(turnover),
        "volume24h": str(volume),
        "openInterestValue": str(open_interest),
        "lastPrice": str(last_price),
        "bid1Price": str(bid_price),
        "ask1Price": str(ask_price),
    }


def test_market_universe_returns_crypto_instruments_only():
    instruments = [
        build_crypto_instrument("BTCUSDT"),
        build_stock_instrument("AAPLUSDT"),
        build_commodity_instrument("XAUUSDT"),
        build_commodity_instrument("CLUSDT"),
    ]

    symbol_config = FakeSymbolConfig(instruments)

    universe = MarketUniverse(
        symbol_config=symbol_config,
    )

    crypto_instruments = (
        universe.get_crypto_instruments()
    )

    symbols = {
        instrument["symbol"]
        for instrument in crypto_instruments
    }

    assert symbols == {"BTCUSDT"}


def test_market_universe_returns_crypto_symbols_only():
    instruments = [
        build_crypto_instrument("BTCUSDT"),
        build_crypto_instrument("ETHUSDT"),
        build_stock_instrument("AAPLUSDT"),
        build_commodity_instrument("XAUUSDT"),
    ]

    universe = MarketUniverse(
        symbol_config=FakeSymbolConfig(
            instruments
        ),
    )

    symbols = universe.get_crypto_symbols()

    assert symbols == [
        "BTCUSDT",
        "ETHUSDT",
    ]


def test_market_universe_filters_low_turnover():
    instruments = [
        build_crypto_instrument("BTCUSDT"),
        build_crypto_instrument("ETHUSDT"),
        build_crypto_instrument("SOLUSDT"),
    ]

    tickers = [
        build_ticker(
            "BTCUSDT",
            10_000_000,
        ),
        build_ticker(
            "ETHUSDT",
            500_000,
        ),
        build_ticker(
            "SOLUSDT",
            2_000_000,
        ),
    ]

    universe = MarketUniverse(
        market_data=FakeMarketData(tickers),
        symbol_config=FakeSymbolConfig(
            instruments
        ),
        min_turnover_24h=1_000_000,
    )

    filtered = universe.filter_tickers(
        tickers
    )

    assert [
        ticker["symbol"]
        for ticker in filtered
    ] == [
        "BTCUSDT",
        "SOLUSDT",
    ]


def test_market_universe_ranks_by_turnover():
    instruments = [
        build_crypto_instrument("BTCUSDT"),
        build_crypto_instrument("ETHUSDT"),
        build_crypto_instrument("SOLUSDT"),
    ]

    tickers = [
        build_ticker(
            "SOLUSDT",
            2_000_000,
        ),
        build_ticker(
            "BTCUSDT",
            10_000_000,
        ),
        build_ticker(
            "ETHUSDT",
            5_000_000,
        ),
    ]

    universe = MarketUniverse(
        market_data=FakeMarketData(tickers),
        symbol_config=FakeSymbolConfig(
            instruments
        ),
        min_turnover_24h=0,
    )

    ranked = universe.rank_tickers(
        tickers
    )

    assert [
        ticker["symbol"]
        for ticker in ranked
    ] == [
        "BTCUSDT",
        "ETHUSDT",
        "SOLUSDT",
    ]


def test_market_universe_respects_max_symbols():
    instruments = [
        build_crypto_instrument("BTCUSDT"),
        build_crypto_instrument("ETHUSDT"),
        build_crypto_instrument("SOLUSDT"),
    ]

    tickers = [
        build_ticker(
            "BTCUSDT",
            10_000_000,
        ),
        build_ticker(
            "ETHUSDT",
            5_000_000,
        ),
        build_ticker(
            "SOLUSDT",
            2_000_000,
        ),
    ]

    market_data = FakeMarketData(tickers)

    universe = MarketUniverse(
        market_data=market_data,
        symbol_config=FakeSymbolConfig(
            instruments
        ),
        min_turnover_24h=0,
        max_symbols=2,
    )

    markets = universe.select()

    assert len(markets) == 2

    assert [
        market["symbol"]
        for market in markets
    ] == [
        "BTCUSDT",
        "ETHUSDT",
    ]


def test_market_universe_excludes_non_crypto_tickers():
    instruments = [
        build_crypto_instrument("BTCUSDT"),
        build_stock_instrument("AAPLUSDT"),
        build_commodity_instrument("XAUUSDT"),
    ]

    tickers = [
        build_ticker(
            "BTCUSDT",
            10_000_000,
        ),
        build_ticker(
            "AAPLUSDT",
            20_000_000,
        ),
        build_ticker(
            "XAUUSDT",
            30_000_000,
        ),
    ]

    universe = MarketUniverse(
        market_data=FakeMarketData(tickers),
        symbol_config=FakeSymbolConfig(
            instruments
        ),
        min_turnover_24h=0,
        max_symbols=50,
    )

    markets = universe.select()

    assert [
        market["symbol"]
        for market in markets
    ] == [
        "BTCUSDT",
    ]


def test_market_universe_ignores_malformed_tickers():
    instruments = [
        build_crypto_instrument("BTCUSDT"),
        build_crypto_instrument("ETHUSDT"),
    ]

    tickers = [
        None,
        {},
        {
            "symbol": None,
            "turnover24h": "5000000",
        },
        {
            "symbol": "ETHUSDT",
            "turnover24h": "not-a-number",
        },
        build_ticker(
            "BTCUSDT",
            10_000_000,
        ),
    ]

    universe = MarketUniverse(
        market_data=FakeMarketData(tickers),
        symbol_config=FakeSymbolConfig(
            instruments
        ),
        min_turnover_24h=0,
    )

    markets = universe.select()

    assert [
        market["symbol"]
        for market in markets
    ] == [
        "BTCUSDT",
    ]


def test_market_universe_returns_required_market_fields():
    instruments = [
        build_crypto_instrument("BTCUSDT"),
    ]

    tickers = [
        build_ticker(
            "BTCUSDT",
            turnover=10_000_000,
            volume=20_000,
            open_interest=3_000_000,
            last_price=100_000,
            bid_price=99_999,
            ask_price=100_001,
        )
    ]

    universe = MarketUniverse(
        market_data=FakeMarketData(tickers),
        symbol_config=FakeSymbolConfig(
            instruments
        ),
        min_turnover_24h=0,
    )

    markets = universe.select()

    assert len(markets) == 1

    market = markets[0]

    assert market == {
        "symbol": "BTCUSDT",
        "turnover24h": 10_000_000.0,
        "volume24h": 20_000.0,
        "openInterestValue": 3_000_000.0,
        "lastPrice": 100_000.0,
        "bid1Price": 99_999.0,
        "ask1Price": 100_001.0,
    }


def test_market_universe_uses_one_ticker_request():
    instruments = [
        build_crypto_instrument("BTCUSDT"),
        build_crypto_instrument("ETHUSDT"),
    ]

    tickers = [
        build_ticker(
            "BTCUSDT",
            10_000_000,
        ),
        build_ticker(
            "ETHUSDT",
            5_000_000,
        ),
    ]

    market_data = FakeMarketData(tickers)

    universe = MarketUniverse(
        market_data=market_data,
        symbol_config=FakeSymbolConfig(
            instruments
        ),
        min_turnover_24h=0,
    )

    universe.select()

    assert market_data.get_tickers_calls == 1


def test_market_universe_rejects_invalid_configuration():
    try:
        MarketUniverse(
            min_turnover_24h=-1,
        )
        assert False
    except ValueError as exc:
        assert "min_turnover_24h" in str(exc)

    try:
        MarketUniverse(
            max_symbols=0,
        )
        assert False
    except ValueError as exc:
        assert "max_symbols" in str(exc)