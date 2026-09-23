from market.candles import CandleData
from smc.liquidity import LiquidityEngine
from smc.displacement import DisplacementEngine
from smc.structure import MarketStructure
from smc.fair_value_gaps import FairValueGapEngine
from smc.order_blocks import OrderBlockEngine
from smc.order_block_context import OrderBlockContextEngine
from strategy.setup_engine import SetupEngine


def main():
    print("=== SETUP CONFLUENCE CAUSALITY TEST ===")

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

    liquidity = liquidity_engine.find_all_liquidity(
        candles
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

    raw_fvgs = fvg_engine.detect_fvgs(
        candles
    )

    raw_obs = ob_engine.detect_order_blocks(
        candles,
        displacement,
    )

    print(f"Candles: {len(candles)}")
    print(f"Liquidity levels: {len(liquidity)}")
    print(
        f"Quality sweeps: {len(quality_sweeps)}"
    )
    print(
        f"Displacement: {len(displacement)}"
    )
    print(
        f"Structure breaks: {len(structure_breaks)}"
    )
    print(f"FVGs: {len(raw_fvgs)}")
    print(f"Raw OBs: {len(raw_obs)}")

    causality_failures = 0
    valid_setups = []
    incomplete_setups = []
    no_trade_setups = []

    print()
    print("=== SETUP CHAINS ===")

    for sweep in quality_sweeps:
        sweep_index = sweep[
            "candle_index"
        ]

        displacement_event = (
            setup_engine.find_displacement_after_sweep(
                sweep,
                displacement,
            )
        )

        if displacement_event is None:
            continue

        displacement_index = (
            displacement_event[
                "candle_index"
            ]
        )

        structure_event = (
            setup_engine.find_structure_after_displacement(
                displacement_event,
                structure_breaks,
            )
        )

        if structure_event is None:
            continue

        structure_index = structure_event[
            "candle_index"
        ]

        causal_fvgs = []

        for fvg in raw_fvgs:
            if (
                fvg["created_at_index"]
                > structure_index
            ):
                continue

            evaluated_fvg = (
                fvg_engine.evaluate_quality(
                    fvg,
                    candles,
                    evaluation_index=structure_index,
                )
            )

            if (
                evaluated_fvg["status"]
                == "invalidated"
            ):
                continue

            if not evaluated_fvg.get(
                "eligible",
                False,
            ):
                continue

            causal_fvgs.append(
                evaluated_fvg
            )

        causal_obs = []

        for ob in raw_obs:
            if (
                ob["created_at_index"]
                > structure_index
            ):
                continue

            evaluated_ob = (
                ob_engine.evaluate_quality(
                    ob,
                    candles,
                    evaluation_index=structure_index,
                )
            )

            if (
                evaluated_ob["status"]
                == "invalidated"
            ):
                continue

            if not evaluated_ob.get(
                "eligible",
                False,
            ):
                continue

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
            ob
            for ob in contextual_obs
            if ob.get(
                "context_eligible",
                False,
            )
        ]

        setup = setup_engine.evaluate_sweep(
            sweep,
            displacement,
            structure_breaks,
            contextual_obs,
            causal_fvgs,
        )

        if not (
            sweep_index
            < displacement_index
            < structure_index
        ):
            causality_failures += 1

        order_block = setup.get(
            "order_block"
        )

        if order_block is not None:
            ob_index = order_block[
                "created_at_index"
            ]

            if ob_index >= structure_index:
                causality_failures += 1

            if (
                order_block.get(
                    "evaluation_index"
                )
                != structure_index
            ):
                causality_failures += 1

            if (
                order_block.get(
                    "structure_index"
                )
                != structure_index
            ):
                causality_failures += 1

        fvg = setup.get("fvg")

        if fvg is not None:
            fvg_index = fvg[
                "created_at_index"
            ]

            if fvg_index > structure_index:
                causality_failures += 1

            if (
                fvg.get(
                    "evaluation_index"
                )
                != structure_index
            ):
                causality_failures += 1

        print(
            {
                "sweep": sweep_index,
                "displacement": displacement_index,
                "structure": structure_index,
                "order_block": (
                    order_block[
                        "created_at_index"
                    ]
                    if order_block
                    else None
                ),
                "fvg": (
                    fvg[
                        "created_at_index"
                    ]
                    if fvg
                    else None
                ),
                "setup_score": setup.get(
                    "setup_score"
                ),
                "setup_status": setup.get(
                    "setup_status"
                ),
            }
        )

        if (
            setup["setup_status"]
            == "valid_setup"
        ):
            valid_setups.append(
                setup
            )

        elif (
            setup["setup_status"]
            == "incomplete_setup"
        ):
            incomplete_setups.append(
                setup
            )

        else:
            no_trade_setups.append(
                setup
            )

    print()
    print("=== RESULTS ===")

    print(
        f"Causality failures: "
        f"{causality_failures}"
    )

    print(
        f"Valid setups: "
        f"{len(valid_setups)}"
    )

    print(
        f"Incomplete setups: "
        f"{len(incomplete_setups)}"
    )

    print(
        f"No-trade setups: "
        f"{len(no_trade_setups)}"
    )

    assert causality_failures == 0

    print()
    print(
        "ALL SETUP CONFLUENCE "
        "CAUSALITY TESTS PASSED"
    )


if __name__ == "__main__":
    main()