from market.candles import CandleData
from smc.displacement import DisplacementEngine
from smc.structure import MarketStructure
from smc.order_blocks import OrderBlockEngine
from smc.order_block_context import OrderBlockContextEngine


def test_order_block_causality():
    candles = CandleData().get_klines(
        "BTCUSDT",
        "15m",
        200,
    )

    displacement_engine = DisplacementEngine()

    displacement = (
        displacement_engine.detect_displacement(
            candles
        )
    )

    structure_engine = MarketStructure(
        swing_length=3
    )

    structure_breaks = (
        structure_engine.detect_breaks(
            candles
        )
    )

    order_block_engine = OrderBlockEngine()

    raw_order_blocks = (
        order_block_engine.detect_order_blocks(
            candles,
            displacement,
        )
    )

    context_engine = OrderBlockContextEngine()

    contextual_order_blocks = (
        context_engine.evaluate_order_blocks(
            raw_order_blocks,
            displacement,
            structure_breaks,
        )
    )

    causal_failures = 0
    lifecycle_failures = 0

    for order_block in contextual_order_blocks:

        structure_event = order_block.get(
            "context_structure_break"
        )

        if structure_event is None:
            continue

        ob_index = order_block[
            "created_at_index"
        ]

        displacement_index = order_block[
            "displacement_index"
        ]

        structure_index = structure_event[
            "candle_index"
        ]

        # --------------------------------------------------
        # TEST 1
        #
        # The causal sequence must always be:
        #
        # Order Block
        #      ↓
        # Displacement
        #      ↓
        # MSS / BOS
        # --------------------------------------------------

        if not (
            ob_index
            < displacement_index
            < structure_index
        ):
            causal_failures += 1

            continue

        # --------------------------------------------------
        # TEST 2
        #
        # Evaluate the OB at the exact candle where
        # structure confirmation occurs.
        #
        # Future candles must not affect the decision.
        # --------------------------------------------------

        evaluated_at_structure = (
            order_block_engine.evaluate_quality(
                order_block,
                candles,
                evaluation_index=structure_index,
            )
        )

        assert isinstance(
            evaluated_at_structure,
            dict,
        )

        assert "status" in evaluated_at_structure
        assert "fill_percentage" in evaluated_at_structure
        assert "quality_score" in evaluated_at_structure
        assert "eligible" in evaluated_at_structure

        # --------------------------------------------------
        # TEST 3
        #
        # The displacement candle itself must NOT count
        # as mitigation of the originating OB.
        #
        # Therefore fill_percentage must be zero
        # at the displacement candle.
        # --------------------------------------------------

        evaluated_at_displacement = (
            order_block_engine.evaluate_quality(
                order_block,
                candles,
                evaluation_index=displacement_index,
            )
        )

        displacement_fill = (
            evaluated_at_displacement[
                "fill_percentage"
            ]
        )

        if displacement_fill != 0:
            lifecycle_failures += 1

    # ------------------------------------------------------
    # FINAL RESULTS
    # ------------------------------------------------------

    assert causal_failures == 0, (
        "Order Block causal ordering is invalid."
    )

    assert lifecycle_failures == 0, (
        "The displacement candle is incorrectly "
        "mitigating its originating Order Block."
    )