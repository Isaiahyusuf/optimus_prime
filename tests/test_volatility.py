import pytest

from market.volatility import VolatilityEngine


def build_candles(
    count,
    high=102.0,
    low=98.0,
    close=100.0,
):
    return [
        {
            "timestamp": index,
            "open": 100.0,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000.0,
        }
        for index in range(count)
    ]


def test_volatility_calculates_true_range():
    candles = [
        {
            "high": 110.0,
            "low": 100.0,
            "close": 105.0,
        },
        {
            "high": 115.0,
            "low": 103.0,
            "close": 110.0,
        },
        {
            "high": 112.0,
            "low": 108.0,
            "close": 109.0,
        },
    ]

    engine = VolatilityEngine(
        atr_period=2,
    )

    ranges = engine.true_range(
        candles
    )

    assert ranges == [
        10.0,
        12.0,
        4.0,
    ]


def test_volatility_calculates_atr():
    candles = [
        {
            "high": 110.0,
            "low": 100.0,
            "close": 105.0,
        },
        {
            "high": 115.0,
            "low": 103.0,
            "close": 110.0,
        },
        {
            "high": 112.0,
            "low": 108.0,
            "close": 109.0,
        },
    ]

    engine = VolatilityEngine(
        atr_period=2,
    )

    atr_values = engine.atr(
        candles
    )

    assert atr_values == [
        11.0,
        8.0,
    ]


def test_volatility_calculates_atr_percent():
    candles = [
        {
            "high": 110.0,
            "low": 100.0,
            "close": 105.0,
        },
        {
            "high": 115.0,
            "low": 103.0,
            "close": 110.0,
        },
        {
            "high": 112.0,
            "low": 108.0,
            "close": 109.0,
        },
    ]

    engine = VolatilityEngine(
        atr_period=2,
    )

    percentages = engine.atr_percent(
        candles
    )

    assert percentages == pytest.approx(
        [
            10.0,
            8.0 / 109.0 * 100.0,
        ]
    )


def test_volatility_classifies_low_volatility():
    candles = build_candles(
        count=14,
        high=100.2,
        low=99.8,
        close=100.0,
    )

    engine = VolatilityEngine(
        atr_period=14,
        low_threshold=0.5,
        high_threshold=2.0,
    )

    result = engine.classify(
        candles
    )

    assert result[
        "classification"
    ] == "LOW"


def test_volatility_classifies_normal_volatility():
    candles = build_candles(
        count=14,
        high=100.5,
        low=99.5,
        close=100.0,
    )

    engine = VolatilityEngine(
        atr_period=14,
        low_threshold=0.5,
        high_threshold=2.0,
    )

    result = engine.classify(
        candles
    )

    assert result[
        "classification"
    ] == "NORMAL"


def test_volatility_classifies_high_volatility():
    candles = build_candles(
        count=14,
        high=103.0,
        low=97.0,
        close=100.0,
    )

    engine = VolatilityEngine(
        atr_period=14,
        low_threshold=0.5,
        high_threshold=2.0,
    )

    result = engine.classify(
        candles
    )

    assert result[
        "classification"
    ] == "HIGH"


def test_volatility_rejects_insufficient_candles():
    candles = build_candles(
        count=13,
    )

    engine = VolatilityEngine(
        atr_period=14,
    )

    with pytest.raises(ValueError):
        engine.atr(candles)


def test_volatility_rejects_malformed_candles():
    candles = build_candles(
        count=14,
    )

    candles[5]["high"] = "invalid"

    engine = VolatilityEngine(
        atr_period=14,
    )

    with pytest.raises(ValueError):
        engine.atr(candles)


def test_volatility_rejects_invalid_candle_range():
    candles = build_candles(
        count=14,
    )

    candles[5]["high"] = 90.0
    candles[5]["low"] = 100.0

    engine = VolatilityEngine(
        atr_period=14,
    )

    with pytest.raises(ValueError):
        engine.atr(candles)


def test_volatility_rejects_invalid_configuration():
    with pytest.raises(ValueError):
        VolatilityEngine(
            atr_period=0,
        )

    with pytest.raises(ValueError):
        VolatilityEngine(
            low_threshold=-1,
        )

    with pytest.raises(ValueError):
        VolatilityEngine(
            low_threshold=2.0,
            high_threshold=2.0,
        )


def test_volatility_is_causal():
    candles = build_candles(
        count=20,
        high=102.0,
        low=98.0,
        close=100.0,
    )

    engine = VolatilityEngine(
        atr_period=14,
    )

    original = engine.atr(
        candles
    )

    modified = [
        dict(candle)
        for candle in candles
    ]

    modified[-1]["high"] = 200.0
    modified[-1]["low"] = 50.0
    modified[-1]["close"] = 125.0

    original_before_last = original[:-1]

    modified_atr = engine.atr(
        modified
    )

    assert modified_atr[
        :-1
    ] == original_before_last


def test_volatility_analyze_returns_expected_structure():
    candles = build_candles(
        count=14,
        high=101.0,
        low=99.0,
        close=100.0,
    )

    engine = VolatilityEngine(
        atr_period=14,
    )

    result = engine.analyze(
        candles
    )

    assert result[
        "status"
    ] == "VOLATILITY_ANALYZED"

    assert "atr" in result
    assert "atr_percent" in result
    assert "classification" in result
    assert result[
        "period"
    ] == 14