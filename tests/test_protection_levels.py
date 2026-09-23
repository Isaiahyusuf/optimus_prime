from risk.protection_levels import (
    ProtectionLevelEngine,
)


def test_protection_levels():
    print(
        "\n=== GUARDIAN PROTECTION LEVEL TEST ==="
    )

    engine = ProtectionLevelEngine(
        minimum_risk_reward=2.0,
        stop_buffer_pct=0.0,
    )

    print("\n=== LONG SETUP ===")

    long_setup = {
        "direction": "long",
        "structure": {
            "price": 95.0,
        },
        "order_block": {
            "low": 96.0,
        },
        "target_liquidity": {
            "price": 112.0,
        },
    }

    long_result = engine.generate(
        long_setup,
        entry_price=100.0,
    )

    print(long_result)

    assert long_result["approved"] is True
    assert long_result["status"] == (
        "PROTECTION_APPROVED"
    )
    assert long_result["direction"] == "long"
    assert long_result["entry_price"] == 100.0
    assert long_result["stop_loss"] == 95.0
    assert long_result["take_profit"] == 112.0
    assert long_result["risk_distance"] == 5.0
    assert long_result["reward_distance"] == 12.0
    assert long_result["risk_reward"] == 2.4

    print("\n=== SHORT SETUP ===")

    short_setup = {
        "direction": "short",
        "structure": {
            "price": 105.0,
        },
        "order_block": {
            "high": 104.0,
        },
        "target_liquidity": {
            "price": 88.0,
        },
    }

    short_result = engine.generate(
        short_setup,
        entry_price=100.0,
    )

    print(short_result)

    assert short_result["approved"] is True
    assert short_result["status"] == (
        "PROTECTION_APPROVED"
    )
    assert short_result["direction"] == "short"
    assert short_result["entry_price"] == 100.0
    assert short_result["stop_loss"] == 105.0
    assert short_result["take_profit"] == 88.0
    assert short_result["risk_distance"] == 5.0
    assert short_result["reward_distance"] == 12.0
    assert short_result["risk_reward"] == 2.4

    print("\n=== LOW R:R TEST ===")

    low_rr_setup = {
        "direction": "long",
        "structure": {
            "price": 95.0,
        },
        "order_block": {
            "low": 95.0,
        },
        "target_liquidity": {
            "price": 102.0,
        },
    }

    low_rr_result = engine.generate(
        low_rr_setup,
        entry_price=100.0,
    )

    print(low_rr_result)

    assert low_rr_result["approved"] is False
    assert low_rr_result["status"] == "NO_TRADE"
    assert low_rr_result["reason"] == (
        "risk_reward_too_low"
    )

    print("\n=== MISSING STOP TEST ===")

    missing_stop_setup = {
        "direction": "long",
        "target_liquidity": {
            "price": 115.0,
        },
    }

    missing_stop_result = engine.generate(
        missing_stop_setup,
        entry_price=100.0,
    )

    print(missing_stop_result)

    assert missing_stop_result["approved"] is False
    assert missing_stop_result["status"] == "NO_TRADE"
    assert missing_stop_result["reason"] == (
        "no_structural_stop_available"
    )

    print(
        "\nALL GUARDIAN PROTECTION LEVEL TESTS PASSED"
    )


if __name__ == "__main__":
    test_protection_levels()