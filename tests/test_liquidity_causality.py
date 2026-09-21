from market.candles import CandleData
from smc.liquidity import LiquidityEngine


def main():
    candles = CandleData().get_klines("BTCUSDT", "15m", 200)

    engine = LiquidityEngine()

    levels = engine.find_all_liquidity(candles)
    sweeps = engine.find_quality_sweeps(candles, levels)

    print("\n=== LIQUIDITY CAUSALITY TEST ===")

    # ---------------------------------------------------------
    # TEST 1: Every swing must be confirmed after it forms
    # ---------------------------------------------------------
    invalid_levels = [
        level
        for level in levels
        if level["confirmed_at_index"] < level["index"]
    ]

    print(f"Liquidity levels: {len(levels)}")
    print(f"Invalid confirmation timing: {len(invalid_levels)}")

    assert not invalid_levels, (
        "FAIL: Some liquidity levels became available before "
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

    print(f"Quality sweeps: {len(sweeps)}")
    print(f"Invalid sweep timing: {len(invalid_sweeps)}")

    assert not invalid_sweeps, (
        "FAIL: A sweep was detected before its liquidity "
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

    print(f"Missing liquidity references: {len(missing_levels)}")

    assert not missing_levels, (
        "FAIL: A sweep references a liquidity level that "
        "does not exist in the detected liquidity set."
    )

    # ---------------------------------------------------------
    # TEST 4: Confirmation timestamp must not precede formation
    # ---------------------------------------------------------
    invalid_timestamps = [
        level
        for level in levels
        if level["confirmation_timestamp"] < level["timestamp"]
    ]

    print(
        f"Invalid timestamp confirmation ordering: "
        f"{len(invalid_timestamps)}"
    )

    assert not invalid_timestamps, (
        "FAIL: A liquidity confirmation timestamp occurs "
        "before the liquidity level timestamp."
    )

    # ---------------------------------------------------------
    # TEST 5: Print representative causal chain
    # ---------------------------------------------------------
    print("\n=== SAMPLE CAUSAL CHAINS ===")

    for sweep in sweeps[:10]:
        print(
            f"Liquidity index={sweep['liquidity_index']} "
            f"confirmed={sweep['liquidity_confirmed_at_index']} "
            f"-> sweep candle={sweep['candle_index']} "
            f"direction={sweep['direction']}"
        )

    print("\n================================")
    print("ALL LIQUIDITY CAUSALITY TESTS PASSED")
    print("================================")


if __name__ == "__main__":
    main()
