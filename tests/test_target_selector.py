from strategy.target_selector import LiquidityTargetSelector


def test_target_selector():
    print(
        "\n=== LIQUIDITY TARGET SELECTOR TEST ==="
    )

    engine = LiquidityTargetSelector(
        minimum_distance_pct=0.001,
    )

    print("\n=== LONG TARGET TEST ===")

    long_setup = {
        "setup_status": "valid_setup",
        "direction": "bullish",
        "decision_index": 20,
    }

    long_liquidity = [
        {
            "type": "buy_side",
            "subtype": "liquidity_cluster",
            "price": 101.0,
            "index": 15,
            "confirmed_at_index": 18,
        },
        {
            "type": "buy_side",
            "subtype": "liquidity_cluster",
            "price": 105.0,
            "index": 18,
            "confirmed_at_index": 20,
        },
        {
            "type": "buy_side",
            "subtype": "liquidity_cluster",
            "price": 110.0,
            "index": 22,
            "confirmed_at_index": 24,
        },
        {
            "type": "sell_side",
            "subtype": "liquidity_cluster",
            "price": 95.0,
            "index": 12,
            "confirmed_at_index": 16,
        },
    ]

    long_result = engine.select_target(
        long_setup,
        long_liquidity,
        entry_price=100.0,
    )

    print(long_result)

    assert long_result["approved"] is True
    assert (
        long_result["status"]
        == "TARGET_READY"
    )
    assert (
        long_result["direction"]
        == "long"
    )

    assert (
        long_result["target_price"]
        == 101.0
    )

    assert (
        long_result[
            "target_confirmed_at_index"
        ]
        == 18
    )

    assert (
        long_result[
            "target_distance"
        ]
        == 1.0
    )

    print(
        "\nLONG TARGET TEST PASSED"
    )

    print("\n=== SHORT TARGET TEST ===")

    short_setup = {
        "setup_status": "valid_setup",
        "direction": "bearish",
        "decision_index": 30,
    }

    short_liquidity = [
        {
            "type": "sell_side",
            "subtype": "liquidity_cluster",
            "price": 99.0,
            "index": 25,
            "confirmed_at_index": 28,
        },
        {
            "type": "sell_side",
            "subtype": "liquidity_cluster",
            "price": 95.0,
            "index": 26,
            "confirmed_at_index": 30,
        },
        {
            "type": "sell_side",
            "subtype": "liquidity_cluster",
            "price": 90.0,
            "index": 35,
            "confirmed_at_index": 35,
        },
        {
            "type": "buy_side",
            "subtype": "liquidity_cluster",
            "price": 110.0,
            "index": 20,
            "confirmed_at_index": 25,
        },
    ]

    short_result = engine.select_target(
        short_setup,
        short_liquidity,
        entry_price=100.0,
    )

    print(short_result)

    assert short_result["approved"] is True
    assert (
        short_result["status"]
        == "TARGET_READY"
    )
    assert (
        short_result["direction"]
        == "short"
    )

    assert (
        short_result["target_price"]
        == 99.0
    )

    assert (
        short_result[
            "target_confirmed_at_index"
        ]
        == 28
    )

    assert (
        short_result[
            "target_distance"
        ]
        == 1.0
    )

    print(
        "\nSHORT TARGET TEST PASSED"
    )

    print(
        "\n=== FUTURE LIQUIDITY REJECTION TEST ==="
    )

    future_setup = {
        "setup_status": "valid_setup",
        "direction": "bullish",
        "decision_index": 20,
    }

    future_liquidity = [
        {
            "type": "buy_side",
            "subtype": "liquidity_cluster",
            "price": 110.0,
            "index": 25,
            "confirmed_at_index": 21,
        }
    ]

    future_result = engine.select_target(
        future_setup,
        future_liquidity,
        entry_price=100.0,
    )

    print(future_result)

    assert (
        future_result["approved"]
        is False
    )

    assert (
        future_result["status"]
        == "NO_TRADE"
    )

    assert (
        future_result["reason"]
        == "no_qualifying_liquidity_target"
    )

    print(
        "\nFUTURE LIQUIDITY REJECTION PASSED"
    )

    print(
        "\n=== WRONG DIRECTION TEST ==="
    )

    wrong_direction_setup = {
        "setup_status": "valid_setup",
        "direction": "bullish",
        "decision_index": 20,
    }

    wrong_direction_liquidity = [
        {
            "type": "sell_side",
            "subtype": "liquidity_cluster",
            "price": 95.0,
            "index": 15,
            "confirmed_at_index": 18,
        }
    ]

    wrong_direction_result = (
        engine.select_target(
            wrong_direction_setup,
            wrong_direction_liquidity,
            entry_price=100.0,
        )
    )

    print(
        wrong_direction_result
    )

    assert (
        wrong_direction_result[
            "approved"
        ]
        is False
    )

    assert (
        wrong_direction_result[
            "status"
        ]
        == "NO_TRADE"
    )

    assert (
        wrong_direction_result[
            "reason"
        ]
        == "no_qualifying_liquidity_target"
    )

    print(
        "\nWRONG DIRECTION TEST PASSED"
    )

    print(
        "\nALL LIQUIDITY TARGET SELECTOR TESTS PASSED"
    )


if __name__ == "__main__":
    test_target_selector()