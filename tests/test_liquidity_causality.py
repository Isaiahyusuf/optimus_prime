from market.candles import CandleData
from smc.liquidity import LiquidityEngine


def test_liquidity_causality():
    candles = CandleData().get_klines(
        "BTCUSDT",
        "15m",
        200,
    )

    engine = LiquidityEngine()

    levels = engine.find_all_liquidity(candles)
    sweeps = engine.find_quality_sweeps(
        candles,
        levels,
    )

    # ---------------------------------------------------------
    # TEST 1: Every swing must be confirmed after it forms
    # ---------------------------------------------------------

    invalid_levels = [
        level
        for level in levels
        if level["confirmed_at_index"] < level["index"]
    ]

    assert not invalid_levels, (
        "Some liquidity levels became available before "
        "their underlying swing was confirmed."
    )

    # ---------------------------------------------------------
    # TEST 2: Every sweep must happen AFTER liquidity exists
    # ---------------------------------------------------------

    invalid_sweeps = [
        sweep
        for sweep in sweeps
        if sweep["candle_index"]
        <= sweep["liquidity_confirmed_at_index"]
    ]

    assert not invalid_sweeps, (
        "A sweep was detected before its liquidity "
        "level was confirmed."
    )

    # ---------------------------------------------------------
    # TEST 3: Every sweep must reference a real liquidity level
    # ---------------------------------------------------------

    level_keys = {
        (
            level["type"],
            level["index"],
            round(level["price"], 8),
        )
        for level in levels
    }

    missing_levels = []

    for sweep in sweeps:
        key = (
            sweep["liquidity_type"],
            sweep["liquidity_index"],
            round(sweep["liquidity_price"], 8),
        )

        if key not in level_keys:
            missing_levels.append(sweep)

    assert not missing_levels, (
        "A sweep references a liquidity level that "
        "does not exist in the detected liquidity set."
    )

    # ---------------------------------------------------------
    # TEST 4: Confirmation timestamp must not precede formation
    # ---------------------------------------------------------

    invalid_timestamps = [
        level
        for level in levels
        if level["confirmation_timestamp"]
        < level["timestamp"]
    ]

    assert not invalid_timestamps, (
        "A liquidity confirmation timestamp occurs "
        "before the liquidity level timestamp."
    )

    # ---------------------------------------------------------
    # TEST 5: Basic output sanity
    # ---------------------------------------------------------

    assert isinstance(levels, list)
    assert isinstance(sweeps, list)

    for level in levels:
        assert level["confirmed_at_index"] >= level["index"]

    for sweep in sweeps:
        assert (
            sweep["candle_index"]
            > sweep["liquidity_confirmed_at_index"]
        )