import pytest

from core.market_regime import MarketRegimeEngine


def build_candles(
    closes,
    high_offset=1.0,
    low_offset=1.0,
):
    candles = []

    for index, close in enumerate(closes):
        candles.append(
            {
                "timestamp": index,
                "open": close,
                "high": close + high_offset,
                "low": close - low_offset,
                "close": close,
                "volume": 1000.0,
            }
        )

    return candles


def test_market_regime_detects_uptrend():
    closes = [
        100.0,
        102.0,
        104.0,
        106.0,
        108.0,
        110.0,
        112.0,
        114.0,
        116.0,
        118.0,
        120.0,
        122.0,
        124.0,
        126.0,
        128.0,
    ]

    engine = MarketRegimeEngine(
        lookback=5,
        trend_threshold=0.03,
    )

    result = engine.analyze(
        build_candles(closes)
    )

    assert result["regime"] == "TRENDING_UP"


def test_market_regime_detects_downtrend():
    closes = [
        130.0,
        128.0,
        126.0,
        124.0,
        122.0,
        120.0,
        118.0,
        116.0,
        114.0,
        112.0,
        110.0,
        108.0,
        106.0,
        104.0,
        102.0,
    ]

    engine = MarketRegimeEngine(
        lookback=5,
        trend_threshold=0.03,
    )

    result = engine.analyze(
        build_candles(closes)
    )

    assert result["regime"] == "TRENDING_DOWN"


def test_market_regime_detects_range():
    closes = [
        100.0,
        102.0,
        99.0,
        101.0,
        100.0,
        98.0,
        101.0,
        99.0,
        100.0,
        102.0,
        99.0,
        101.0,
        100.0,
        98.0,
        100.0,
    ]

    engine = MarketRegimeEngine(
        lookback=5,
        trend_threshold=0.03,
    )

    result = engine.analyze(
        build_candles(closes)
    )

    assert result["regime"] == "RANGING"


def test_market_regime_detects_transition():
    closes = [
        100.0,
        100.5,
        99.5,
        101.0,
        100.0,
        101.5,
        100.5,
        102.0,
        101.0,
        102.5,
        101.5,
        103.0,
        102.0,
        103.5,
        103.0,
    ]

    engine = MarketRegimeEngine(
        lookback=5,
        trend_threshold=0.03,
    )

    result = engine.analyze(
        build_candles(closes)
    )

    assert result["regime"] == "TRANSITION"


def test_market_regime_requires_enough_candles():
    closes = [
        100.0,
        101.0,
        102.0,
        103.0,
    ]

    engine = MarketRegimeEngine(
        lookback=5,
    )

    with pytest.raises(ValueError):
        engine.analyze(
            build_candles(closes)
        )


def test_market_regime_rejects_invalid_lookback():
    with pytest.raises(ValueError):
        MarketRegimeEngine(
            lookback=0,
        )


def test_market_regime_rejects_invalid_threshold():
    with pytest.raises(ValueError):
        MarketRegimeEngine(
            trend_threshold=0,
        )

    with pytest.raises(ValueError):
        MarketRegimeEngine(
            trend_threshold=-0.01,
        )


def test_market_regime_rejects_malformed_candles():
    candles = build_candles(
        [
            100.0,
            101.0,
            102.0,
            103.0,
            104.0,
            105.0,
        ]
    )

    candles[2]["close"] = "invalid"

    engine = MarketRegimeEngine(
        lookback=5,
    )

    with pytest.raises(ValueError):
        engine.analyze(candles)


def test_market_regime_is_causal():
    closes = [
        100.0,
        102.0,
        104.0,
        106.0,
        108.0,
        110.0,
        112.0,
        114.0,
        116.0,
        118.0,
        120.0,
    ]

    candles = build_candles(closes)

    engine = MarketRegimeEngine(
        lookback=5,
        trend_threshold=0.03,
    )

    prefix = candles[:-1]

    original = engine.analyze(prefix)

    modified = [
        dict(candle)
        for candle in candles
    ]

    modified[-1]["close"] = 50.0
    modified[-1]["high"] = 51.0
    modified[-1]["low"] = 49.0

    modified_prefix = modified[:-1]

    modified_result = engine.analyze(
        modified_prefix
    )

    assert modified_result == original


def test_market_regime_returns_expected_structure():
    closes = [
        100.0,
        102.0,
        104.0,
        106.0,
        108.0,
        110.0,
        112.0,
        114.0,
        116.0,
        118.0,
    ]

    engine = MarketRegimeEngine(
        lookback=5,
        trend_threshold=0.03,
    )

    result = engine.analyze(
        build_candles(closes)
    )

    assert result["status"] == "REGIME_ANALYZED"
    assert "regime" in result
    assert "directional_change" in result
    assert "efficiency_ratio" in result
    assert "directional_consistency" in result
    assert "broader_directional_change" in result
    assert "lookback" in result
    assert "trend_threshold" in result
    assert "trend_efficiency_threshold" in result
    assert "transition_efficiency_threshold" in result


def test_market_regime_future_candle_cannot_change_prefix_analysis():
    closes = [
        100.0,
        102.0,
        104.0,
        106.0,
        108.0,
        110.0,
        112.0,
        114.0,
        116.0,
        118.0,
    ]

    candles = build_candles(closes)

    engine = MarketRegimeEngine(
        lookback=5,
        trend_threshold=0.03,
    )

    prefix = candles[:-1]

    before_future_candle = engine.analyze(
        prefix
    )

    modified_future = [
        dict(candle)
        for candle in candles
    ]

    modified_future[-1]["open"] = 50.0
    modified_future[-1]["high"] = 60.0
    modified_future[-1]["low"] = 40.0
    modified_future[-1]["close"] = 50.0
    modified_future[-1]["volume"] = 999999.0

    after_future_candle = engine.analyze(
        modified_future[:-1]
    )

    assert after_future_candle == before_future_candle


def test_market_regime_is_deterministic():
    closes = [
        100.0,
        101.0,
        102.0,
        101.0,
        103.0,
        104.0,
        105.0,
        106.0,
        107.0,
        108.0,
    ]

    candles = build_candles(closes)

    engine = MarketRegimeEngine(
        lookback=5,
        trend_threshold=0.03,
    )

    first = engine.analyze(candles)
    second = engine.analyze(candles)

    assert first == second


def test_market_regime_detects_flat_market_as_range():
    closes = [
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
    ]

    engine = MarketRegimeEngine(
        lookback=5,
        trend_threshold=0.03,
    )

    result = engine.analyze(
        build_candles(closes)
    )

    assert result["regime"] == "RANGING"
    assert result["directional_change"] == 0.0
    assert result["efficiency_ratio"] == 0.0


def test_market_regime_detects_choppy_directional_market_as_transition():
    closes = [
        100.0,
        103.0,
        99.0,
        104.0,
        100.0,
        105.0,
        101.0,
        106.0,
        102.0,
        107.0,
    ]

    engine = MarketRegimeEngine(
        lookback=5,
        trend_threshold=0.03,
    )

    result = engine.analyze(
        build_candles(closes)
    )

    assert result["regime"] == "TRANSITION"


def test_market_regime_rejects_missing_candle_fields():
    candles = build_candles(
        [
            100.0,
            101.0,
            102.0,
            103.0,
            104.0,
            105.0,
        ]
    )

    del candles[2]["close"]

    engine = MarketRegimeEngine(
        lookback=5,
    )

    with pytest.raises(ValueError):
        engine.analyze(candles)


def test_market_regime_rejects_negative_volume():
    candles = build_candles(
        [
            100.0,
            101.0,
            102.0,
            103.0,
            104.0,
            105.0,
        ]
    )

    candles[3]["volume"] = -1.0

    engine = MarketRegimeEngine(
        lookback=5,
    )

    with pytest.raises(ValueError):
        engine.analyze(candles)


def test_market_regime_rejects_invalid_ohlc_relationship():
    candles = build_candles(
        [
            100.0,
            101.0,
            102.0,
            103.0,
            104.0,
            105.0,
        ]
    )

    candles[3]["high"] = 90.0
    candles[3]["low"] = 100.0

    engine = MarketRegimeEngine(
        lookback=5,
    )

    with pytest.raises(ValueError):
        engine.analyze(candles)


def test_market_regime_rejects_non_positive_close():
    candles = build_candles(
        [
            100.0,
            101.0,
            102.0,
            103.0,
            104.0,
            105.0,
        ]
    )

    candles[3]["close"] = 0.0

    engine = MarketRegimeEngine(
        lookback=5,
    )

    with pytest.raises(ValueError):
        engine.analyze(candles)


def test_market_regime_rejects_invalid_efficiency_configuration():
    with pytest.raises(ValueError):
        MarketRegimeEngine(
            trend_efficiency_threshold=0,
        )

    with pytest.raises(ValueError):
        MarketRegimeEngine(
            trend_efficiency_threshold=1.1,
        )

    with pytest.raises(ValueError):
        MarketRegimeEngine(
            transition_efficiency_threshold=-0.1,
        )

    with pytest.raises(ValueError):
        MarketRegimeEngine(
            transition_efficiency_threshold=1.1,
        )

    with pytest.raises(ValueError):
        MarketRegimeEngine(
            trend_efficiency_threshold=0.5,
            transition_efficiency_threshold=0.5,
        )


def test_market_regime_returns_bounded_efficiency_metrics():
    closes = [
        100.0,
        101.0,
        99.0,
        102.0,
        100.0,
        103.0,
        101.0,
        104.0,
        102.0,
        105.0,
    ]

    engine = MarketRegimeEngine(
        lookback=5,
        trend_threshold=0.03,
    )

    result = engine.analyze(
        build_candles(closes)
    )

    assert 0.0 <= result[
        "efficiency_ratio"
    ] <= 1.0

    assert 0.0 <= result[
        "directional_consistency"
    ] <= 1.0