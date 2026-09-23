from risk.protection import ProtectionEngine


def test_protection_engine():
    print("\n=== GUARDIAN PROTECTION TEST ===")

    engine = ProtectionEngine(
        minimum_risk_reward=2.0,
        minimum_stop_distance_pct=0.001,
    )

    print("\n=== LONG TEST ===")

    long_result = engine.evaluate(
        "long",
        100.0,
        95.0,
        110.0,
    )

    print(long_result)

    assert long_result["approved"] is True
    assert long_result["direction"] == "long"
    assert long_result["risk_distance"] == 5.0
    assert long_result["reward_distance"] == 10.0
    assert long_result["risk_reward"] == 2.0

    print("\n=== SHORT TEST ===")

    short_result = engine.evaluate(
        "short",
        100.0,
        105.0,
        90.0,
    )

    print(short_result)

    assert short_result["approved"] is True
    assert short_result["direction"] == "short"
    assert short_result["risk_distance"] == 5.0
    assert short_result["reward_distance"] == 10.0
    assert short_result["risk_reward"] == 2.0

    print("\n=== INVALID LONG TEST ===")

    invalid_long = engine.evaluate(
        "long",
        100.0,
        105.0,
        110.0,
    )

    print(invalid_long)

    assert invalid_long["approved"] is False
    assert (
        invalid_long["reason"]
        == "long_stop_must_be_below_entry"
    )

    print("\n=== INVALID SHORT TEST ===")

    invalid_short = engine.evaluate(
        "short",
        100.0,
        95.0,
        90.0,
    )

    print(invalid_short)

    assert invalid_short["approved"] is False
    assert (
        invalid_short["reason"]
        == "short_stop_must_be_above_entry"
    )

    print("\n=== LOW R:R TEST ===")

    low_rr = engine.evaluate(
        "long",
        100.0,
        95.0,
        102.0,
    )

    print(low_rr)

    assert low_rr["approved"] is False
    assert low_rr["reason"] == "risk_reward_too_low"

    print(
        "\nALL GUARDIAN PROTECTION TESTS PASSED"
    )


if __name__ == "__main__":
    test_protection_engine()