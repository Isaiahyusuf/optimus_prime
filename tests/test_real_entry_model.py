from market.candles import CandleData
from smc.liquidity import LiquidityEngine
from smc.displacement import DisplacementEngine
from smc.structure import MarketStructure
from smc.fair_value_gaps import FairValueGapEngine
from smc.order_blocks import OrderBlockEngine
from smc.order_block_context import OrderBlockContextEngine
from strategy.setup_engine import SetupEngine
from strategy.entry_model import SMCEntryModel


def build_deterministic_entry_setup():
    return {
        "setup_status": "valid_setup",
        "direction": "bullish",
        "decision_index": 30,
        "sweep": {
            "candle_index": 20,
            "direction": "bullish",
        },
        "displacement": {
            "candle_index": 23,
            "direction": "bullish",
        },
        "structure": {
            "candle_index": 27,
            "direction": "bullish",
        },
        "order_block": {
            "direction": "bullish",
            "created_at_index": 22,
            "evaluation_index": 30,
            "structure_index": 27,
            "low": 100.0,
            "high": 110.0,
            "eligible": True,
            "context_eligible": True,
            "status": "active",
        },
        "fvg": {
            "direction": "bullish",
            "created_at_index": 23,
            "evaluation_index": 30,
            "gap_low": 105.0,
            "gap_high": 108.0,
            "eligible": True,
            "status": "active",
        },
        "setup_score": 100,
    }


def test_real_entry_model():
    print(
        "\n=== OPTIMUS REAL SMC ENTRY MODEL TEST ==="
    )

    entry_engine = SMCEntryModel(
        use_fvg_refinement=True,
    )

    print(
        "\n=== DETERMINISTIC SMC ENTRY TEST ==="
    )

    setup = build_deterministic_entry_setup()

    entry_result = entry_engine.generate(
        setup
    )

    print(
        {
            "setup_status": setup["setup_status"],
            "direction": setup["direction"],
            "decision_index": setup["decision_index"],
            "entry_result": entry_result,
        }
    )

    assert entry_result["approved"] is True

    assert (
        entry_result["status"]
        == "ENTRY_ZONE_READY"
    )

    assert (
        entry_result["direction"]
        == "long"
    )

    entry_low = entry_result[
        "entry_zone_low"
    ]

    entry_high = entry_result[
        "entry_zone_high"
    ]

    candidate_entry = entry_result[
        "candidate_entry"
    ]

    assert entry_low == 105.0
    assert entry_high == 108.0
    assert candidate_entry == 106.5

    assert entry_low > 0
    assert entry_high > entry_low

    assert (
        entry_low
        <= candidate_entry
        <= entry_high
    )

    assert (
        entry_result["entry_zone_source"]
        == "order_block_fvg_overlap"
    )

    assert (
        entry_result["order_block_low"]
        == 100.0
    )

    assert (
        entry_result["order_block_high"]
        == 110.0
    )

    assert (
        entry_result["fvg_low"]
        == 105.0
    )

    assert (
        entry_result["fvg_high"]
        == 108.0
    )

    print(
        "\nDETERMINISTIC ENTRY MODEL TEST PASSED"
    )

    print(
        "\n=== LIVE BTCUSDT SMC SCAN ==="
    )

    candles = CandleData().get_klines(
        "BTCUSDT",
        "15m",
        200,
    )

    liquidity_engine = LiquidityEngine()
    displacement_engine = DisplacementEngine()
    structure_engine = MarketStructure()
    fvg_engine = FairValueGapEngine()
    ob_engine = OrderBlockEngine()
    context_engine = OrderBlockContextEngine()
    setup_engine = SetupEngine()

    liquidity = (
        liquidity_engine.find_all_liquidity(
            candles
        )
    )

    quality_sweeps = (
        liquidity_engine.find_quality_sweeps(
            candles,
            liquidity,
        )
    )

    displacement = (
        displacement_engine.detect_displacement(
            candles
        )
    )

    structure_breaks = (
        structure_engine.detect_breaks(
            candles
        )
    )

    raw_fvgs = (
        fvg_engine.detect_fvgs(
            candles
        )
    )

    raw_obs = (
        ob_engine.detect_order_blocks(
            candles,
            displacement,
        )
    )

    print(
        f"Candles: {len(candles)}"
    )
    print(
        f"Liquidity levels: {len(liquidity)}"
    )
    print(
        f"Quality sweeps: {len(quality_sweeps)}"
    )
    print(
        f"Displacement: {len(displacement)}"
    )
    print(
        f"Structure breaks: {len(structure_breaks)}"
    )
    print(
        f"FVGs: {len(raw_fvgs)}"
    )
    print(
        f"Raw OBs: {len(raw_obs)}"
    )

    valid_setups = []

    print(
        "\n=== LIVE SMC SETUP CHAINS ==="
    )

    for sweep in quality_sweeps:
        sweep_index = sweep.get(
            "candle_index"
        )

        if sweep_index is None:
            continue

        displacement_event = (
            setup_engine.find_displacement_after_sweep(
                sweep,
                displacement,
            )
        )

        if displacement_event is None:
            continue

        displacement_index = (
            displacement_event.get(
                "candle_index"
            )
        )

        if displacement_index is None:
            continue

        structure_event = (
            setup_engine.find_structure_after_displacement(
                displacement_event,
                structure_breaks,
            )
        )

        if structure_event is None:
            continue

        structure_index = (
            structure_event.get(
                "candle_index"
            )
        )

        if structure_index is None:
            continue

        if not (
            sweep_index
            < displacement_index
            < structure_index
        ):
            continue

        causal_fvgs = []

        for fvg in raw_fvgs:
            created_at_index = fvg.get(
                "created_at_index"
            )

            if created_at_index is None:
                continue

            if created_at_index > structure_index:
                continue

            evaluated_fvg = (
                fvg_engine.evaluate_quality(
                    fvg,
                    candles,
                    evaluation_index=structure_index,
                )
            )

            if evaluated_fvg.get(
                "status"
            ) == "invalidated":
                continue

            if not evaluated_fvg.get(
                "eligible",
                False,
            ):
                continue

            evaluated_fvg[
                "evaluation_index"
            ] = structure_index

            causal_fvgs.append(
                evaluated_fvg
            )

        causal_obs = []

        for order_block in raw_obs:
            created_at_index = (
                order_block.get(
                    "created_at_index"
                )
            )

            if created_at_index is None:
                continue

            if created_at_index > structure_index:
                continue

            evaluated_ob = (
                ob_engine.evaluate_quality(
                    order_block,
                    candles,
                    evaluation_index=structure_index,
                )
            )

            if evaluated_ob.get(
                "status"
            ) == "invalidated":
                continue

            if not evaluated_ob.get(
                "eligible",
                False,
            ):
                continue

            evaluated_ob[
                "evaluation_index"
            ] = structure_index

            causal_obs.append(
                evaluated_ob
            )

        contextual_obs = (
            context_engine.evaluate_order_blocks(
                causal_obs,
                displacement,
                structure_breaks,
            )
        )

        contextual_obs = [
            order_block
            for order_block in contextual_obs
            if order_block.get(
                "context_eligible",
                False,
            )
        ]

        setup_result = (
            setup_engine.evaluate_sweep(
                sweep,
                displacement,
                structure_breaks,
                contextual_obs,
                causal_fvgs,
            )
        )

        if (
            setup_result.get(
                "setup_status"
            )
            != "valid_setup"
        ):
            continue

        order_block = setup_result.get(
            "order_block"
        )

        fvg = setup_result.get(
            "fvg"
        )

        if not isinstance(
            order_block,
            dict,
        ):
            continue

        if not isinstance(
            fvg,
            dict,
        ):
            continue

        if (
            order_block.get(
                "created_at_index"
            )
            > structure_index
        ):
            raise AssertionError(
                "Order Block uses future data"
            )

        if (
            order_block.get(
                "evaluation_index"
            )
            != structure_index
        ):
            raise AssertionError(
                "Order Block evaluation index is not causal"
            )

        if (
            order_block.get(
                "structure_index"
            )
            != structure_index
        ):
            raise AssertionError(
                "Order Block structure confirmation is not causal"
            )

        if (
            fvg.get(
                "created_at_index"
            )
            > structure_index
        ):
            raise AssertionError(
                "FVG uses future data"
            )

        if (
            fvg.get(
                "evaluation_index"
            )
            != structure_index
        ):
            raise AssertionError(
                "FVG evaluation index is not causal"
            )

        setup_result["decision_index"] = (
            structure_index
        )

        setup_result["direction"] = (
            structure_event.get(
                "direction"
            )
        )

        live_entry_result = (
            entry_engine.generate(
                setup_result
            )
        )

        print(
            {
                "sweep": sweep_index,
                "displacement": displacement_index,
                "structure": structure_index,
                "order_block": order_block.get(
                    "created_at_index"
                ),
                "fvg": fvg.get(
                    "created_at_index"
                ),
                "setup_score": setup_result.get(
                    "setup_score"
                ),
                "entry_result": live_entry_result,
            }
        )

        if live_entry_result.get(
            "approved"
        ) is not True:
            continue

        assert (
            live_entry_result["status"]
            == "ENTRY_ZONE_READY"
        )

        live_entry_low = (
            live_entry_result[
                "entry_zone_low"
            ]
        )

        live_entry_high = (
            live_entry_result[
                "entry_zone_high"
            ]
        )

        live_candidate_entry = (
            live_entry_result[
                "candidate_entry"
            ]
        )

        assert live_entry_low > 0

        assert (
            live_entry_high
            > live_entry_low
        )

        assert (
            live_entry_low
            <= live_candidate_entry
            <= live_entry_high
        )

        valid_setups.append(
            {
                "setup": setup_result,
                "entry": live_entry_result,
            }
        )

    print(
        "\n=== LIVE ENTRY MODEL RESULTS ==="
    )

    print(
        f"Valid live SMC setups: "
        f"{len(valid_setups)}"
    )

    if len(valid_setups) == 0:
        print(
            "No complete causal SMC entry setup "
            "exists in the current BTCUSDT sample."
        )

        print(
            "This is a valid NO-TRADE market condition."
        )
    else:
        print(
            "At least one complete causal SMC "
            "entry setup was found."
        )

    print(
        "\n=== RETRACEMENT CHECK ==="
    )

    retracement_checks = 0
    retracement_hits = 0

    for item in valid_setups:
        live_setup = item["setup"]
        live_entry = item["entry"]

        decision_index = live_setup[
            "decision_index"
        ]

        entry_low = live_entry[
            "entry_zone_low"
        ]

        entry_high = live_entry[
            "entry_zone_high"
        ]

        direction = live_entry[
            "direction"
        ]

        hit = False
        first_hit_index = None

        for index in range(
            decision_index + 1,
            len(candles),
        ):
            candle = candles[index]

            candle_low = float(
                candle["low"]
            )

            candle_high = float(
                candle["high"]
            )

            retracement_checks += 1

            if (
                candle_low <= entry_high
                and candle_high >= entry_low
            ):
                hit = True
                first_hit_index = index
                retracement_hits += 1
                break

        print(
            {
                "decision_index": decision_index,
                "direction": direction,
                "entry_zone_low": entry_low,
                "entry_zone_high": entry_high,
                "candidate_entry": live_entry[
                    "candidate_entry"
                ],
                "retracement_hit": hit,
                "first_hit_index": first_hit_index,
            }
        )

    print(
        "\n=== FINAL RESULTS ==="
    )

    print(
        "Deterministic entry model: PASSED"
    )

    print(
        f"Live valid setups: "
        f"{len(valid_setups)}"
    )

    print(
        f"Retracement checks: "
        f"{retracement_checks}"
    )

    print(
        f"Retracement hits: "
        f"{retracement_hits}"
    )

    print(
        "\nCAUSALITY CHECK: PASSED"
    )

    print(
        "ENTRY MODEL CHECK: PASSED"
    )

    if retracement_hits > 0:
        print(
            "REAL RETRACEMENT: FOUND"
        )
    else:
        print(
            "REAL RETRACEMENT: NONE IN CURRENT SAMPLE"
        )

    print(
        "\nALL REAL SMC ENTRY MODEL TESTS PASSED"
    )


if __name__ == "__main__":
    test_real_entry_model()