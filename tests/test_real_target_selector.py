from market.candles import CandleData
from smc.liquidity import LiquidityEngine
from smc.displacement import DisplacementEngine
from smc.structure import MarketStructure
from smc.fair_value_gaps import FairValueGapEngine
from smc.order_blocks import OrderBlockEngine
from smc.order_block_context import OrderBlockContextEngine
from strategy.setup_engine import SetupEngine
from strategy.entry_model import SMCEntryModel
from strategy.target_selector import LiquidityTargetSelector


def test_real_target_selector():
    print(
        "\n=== OPTIMUS REAL SMC TARGET SELECTOR TEST ==="
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
    entry_engine = SMCEntryModel(
        use_fvg_refinement=True
    )
    target_engine = LiquidityTargetSelector(
        minimum_distance_pct=0.001
    )

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
        "\n=== REAL SMC SETUP CHAINS ==="
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

            if (
                evaluated_fvg.get(
                    "status"
                )
                == "invalidated"
            ):
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

            if (
                evaluated_ob.get(
                    "status"
                )
                == "invalidated"
            ):
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

        setup = (
            setup_engine.evaluate_sweep(
                sweep,
                displacement,
                structure_breaks,
                contextual_obs,
                causal_fvgs,
            )
        )

        if (
            setup.get(
                "setup_status"
            )
            != "valid_setup"
        ):
            continue

        setup["decision_index"] = (
            structure_index
        )

        setup["direction"] = (
            structure_event.get(
                "direction"
            )
        )

        entry_result = (
            entry_engine.generate(
                setup
            )
        )

        if not entry_result.get(
            "approved",
            False,
        ):
            continue

        candidate_entry = (
            entry_result[
                "candidate_entry"
            ]
        )

        setup["entry_price"] = (
            candidate_entry
        )

        target_result = (
            target_engine.select_target(
                setup,
                liquidity,
                entry_price=candidate_entry,
            )
        )

        print(
            {
                "sweep": sweep_index,
                "displacement": displacement_index,
                "structure": structure_index,
                "entry_zone": (
                    entry_result[
                        "entry_zone_low"
                    ],
                    entry_result[
                        "entry_zone_high"
                    ],
                ),
                "candidate_entry": candidate_entry,
                "target": target_result,
            }
        )

        if target_result.get(
            "approved",
            False,
        ):
            target_price = (
                target_result[
                    "target_price"
                ]
            )

            if setup["direction"] == "bullish":
                assert (
                    target_price
                    > candidate_entry
                )

            elif setup["direction"] == "bearish":
                assert (
                    target_price
                    < candidate_entry
                )

            confirmed_at_index = (
                target_result[
                    "target_confirmed_at_index"
                ]
            )

            assert (
                confirmed_at_index
                <= structure_index
            )

            valid_setups.append(
                {
                    "setup": setup,
                    "entry": entry_result,
                    "target": target_result,
                }
            )

    print(
        "\n=== FINAL RESULTS ==="
    )

    print(
        f"Valid SMC setups with entry: "
        f"{len(valid_setups)}"
    )

    for item in valid_setups:
        print(
            {
                "direction": item[
                    "entry"
                ]["direction"],
                "candidate_entry": item[
                    "entry"
                ]["candidate_entry"],
                "target_price": item[
                    "target"
                ]["target_price"],
                "target_distance": item[
                    "target"
                ]["target_distance"],
                "target_distance_pct": item[
                    "target"
                ]["target_distance_pct"],
                "decision_index": item[
                    "setup"
                ]["decision_index"],
                "target_confirmed_at_index": item[
                    "target"
                ]["target_confirmed_at_index"],
            }
        )

    print(
        "\nCAUSALITY CHECK: PASSED"
    )

    if valid_setups:
        print(
            "REAL ENTRY + TARGET: FOUND"
        )
    else:
        print(
            "REAL ENTRY + TARGET: NONE "
            "IN CURRENT SAMPLE"
        )

    print(
        "\nALL REAL SMC TARGET SELECTOR "
        "TESTS PASSED"
    )


if __name__ == "__main__":
    test_real_target_selector()