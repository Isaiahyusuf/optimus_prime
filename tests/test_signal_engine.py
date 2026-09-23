from strategy.signal_engine import SignalEngine


class FakeMarketRegimeEngine:
    def __init__(self):
        self.received_candles = None

    def analyze(self, candles):
        self.received_candles = candles

        return {
            "status": "REGIME_ANALYZED",
            "regime": "TRENDING_UP",
            "directional_change": 0.05,
            "efficiency_ratio": 0.80,
            "directional_consistency": 0.75,
            "broader_directional_change": 0.10,
            "lookback": 20,
            "trend_threshold": 0.02,
            "trend_efficiency_threshold": 0.60,
            "transition_efficiency_threshold": 0.20,
        }


class FailingMarketRegimeEngine:
    def analyze(self, candles):
        raise RuntimeError(
            "regime calculation failed"
        )


def make_candles(count=10):
    return [
        {
            "timestamp": index,
            "open": 100.0 + index,
            "high": 101.0 + index,
            "low": 99.0 + index,
            "close": 100.5 + index,
            "volume": 1000.0 + (index * 100),
        }
        for index in range(1, count + 1)
    ]


def test_signal_engine_rejects_invalid_candles():
    engine = SignalEngine()

    result = engine.analyze([])

    assert result["success"] is False
    assert result["status"] == "NO_SIGNAL"
    assert result["reason"] == "invalid_candles"
    assert result["candles"] == []
    assert result["market_regime"] is None
    assert result["valid_setups"] == []


def test_signal_engine_analyzes_market_data():
    engine = SignalEngine()

    candles = make_candles(10)

    result = engine.analyze(candles)

    assert result["success"] is True
    assert result["status"] in {
        "SIGNALS_FOUND",
        "NO_SIGNAL",
    }

    assert isinstance(result["candles"], list)
    assert isinstance(result["liquidity"], list)
    assert isinstance(result["sweeps"], list)
    assert isinstance(result["displacement"], list)
    assert isinstance(result["structure_breaks"], list)
    assert result["market_regime"] is None
    assert isinstance(result["order_blocks"], list)
    assert isinstance(
        result["contextual_order_blocks"],
        list,
    )
    assert isinstance(result["fvgs"], list)
    assert isinstance(result["setups"], list)
    assert isinstance(result["valid_setups"], list)


def test_signal_engine_includes_market_regime_context():
    regime_engine = FakeMarketRegimeEngine()

    engine = SignalEngine(
        market_regime_engine=regime_engine
    )

    candles = make_candles(25)

    result = engine.analyze(candles)

    assert result["success"] is True

    assert result["market_regime"] is not None
    assert (
        result["market_regime"]["status"]
        == "REGIME_ANALYZED"
    )
    assert (
        result["market_regime"]["regime"]
        == "TRENDING_UP"
    )

    assert (
        regime_engine.received_candles
        is candles
    )


def test_signal_engine_market_regime_does_not_change_setups():
    candles = make_candles(25)

    engine_without_regime = SignalEngine(
        market_regime_engine=(
            FailingMarketRegimeEngine()
        )
    )

    engine_with_regime = SignalEngine(
        market_regime_engine=(
            FakeMarketRegimeEngine()
        )
    )

    result_without_regime = (
        engine_without_regime.analyze(
            candles
        )
    )

    result_with_regime = (
        engine_with_regime.analyze(
            candles
        )
    )

    assert (
        result_without_regime["valid_setups"]
        == result_with_regime["valid_setups"]
    )

    assert (
        result_without_regime["setups"]
        == result_with_regime["setups"]
    )


def test_signal_engine_market_regime_failure_is_non_blocking():
    engine = SignalEngine(
        market_regime_engine=(
            FailingMarketRegimeEngine()
        )
    )

    candles = make_candles(25)

    result = engine.analyze(candles)

    assert result["success"] is True
    assert result["market_regime"] is None
    assert isinstance(
        result["setups"],
        list,
    )
    assert isinstance(
        result["valid_setups"],
        list,
    )


def test_signal_engine_get_valid_setups():
    engine = SignalEngine()

    candles = make_candles(10)

    valid_setups = engine.get_valid_setups(
        candles
    )

    assert isinstance(valid_setups, list)

    for setup in valid_setups:
        assert setup["setup_status"] == (
            "valid_setup"
        )


def test_signal_engine_latest_setup_returns_none_when_empty():
    engine = SignalEngine()

    result = engine.get_latest_valid_setup([])

    assert result is None


def test_signal_engine_latest_setup_matches_latest_structure():
    engine = SignalEngine()

    engine.get_valid_setups = (
        lambda candles: [
            {
                "setup_status": "valid_setup",
                "structure": {
                    "candle_index": 10,
                },
            },
            {
                "setup_status": "valid_setup",
                "structure": {
                    "candle_index": 25,
                },
            },
            {
                "setup_status": "valid_setup",
                "structure": {
                    "candle_index": 18,
                },
            },
        ]
    )

    result = engine.get_latest_valid_setup([])

    assert result is not None
    assert (
        result["structure"]["candle_index"]
        == 25
    )