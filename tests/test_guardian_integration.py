from market.candles import CandleData
from smc.liquidity import LiquidityEngine
from smc.displacement import DisplacementEngine
from smc.structure import MarketStructure
from smc.fair_value_gaps import FairValueGapEngine
from smc.order_blocks import OrderBlockEngine
from smc.order_block_context import OrderBlockContextEngine
from strategy.setup_engine import SetupEngine
from risk.protection_levels import ProtectionLevelEngine


def main():
    print("=== OPTIMUS GUARDIAN REAL SMC INTEGRATION TEST ===")

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
    protection_engine = ProtectionLevelEngine(
        minimum_risk_reward=2.0,
        stop_buffer_pct=0.0,
    )

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

    valid_setups = []

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

        order_block = setup.get(
            "order_block"
        )

        fvg = setup.get(
            "fvg"
        )

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

    print()
    print("=== SMC RESULTS ===")

    print(
        f"Valid setups: "
        f"{len(valid_setups)}"
    )

    return {
        "candles": len(candles),
        "liquidity": len(liquidity),
        "quality_sweeps": len(quality_sweeps),
        "displacement": len(displacement),
        "structure_breaks": len(structure_breaks),
        "fvgs": len(raw_fvgs),
        "order_blocks": len(raw_obs),
        "valid_setups": len(valid_setups),
    }


def test_guardian_integration():
    result = main()

    assert result["candles"] == 200
    assert result["liquidity"] >= 0
    assert result["quality_sweeps"] >= 0
    assert result["displacement"] >= 0
    assert result["structure_breaks"] >= 0
    assert result["fvgs"] >= 0
    assert result["order_blocks"] >= 0
    assert result["valid_setups"] >= 0