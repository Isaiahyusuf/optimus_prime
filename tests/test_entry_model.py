from strategy.entry_model import SMCEntryModel


def test_entry_model():
    print(
        "\n=== SMC ENTRY MODEL TEST ==="
    )

    engine = SMCEntryModel(
        use_fvg_refinement=True,
    )

    print("\n=== LONG SETUP ===")

    long_setup = {
        "setup_status": "valid_setup",
        "direction": "bullish",
        "order_block": {
            "direction": "bullish",
            "low": 100.0,
            "high": 110.0,
        },
        "fvg": {
            "direction": "bullish",
            "gap_low": 105.0,
            "gap_high": 108.0,
        },
    }

    long_result = engine.generate(
        long_setup
    )

    print(long_result)

    assert long_result["approved"] is True
    assert (
        long_result["status"]
        == "ENTRY_ZONE_READY"
    )
    assert (
        long_result["direction"]
        == "long"
    )
    assert (
        long_result["entry_zone_low"]
        == 105.0
    )
    assert (
        long_result["entry_zone_high"]
        == 108.0
    )
    assert (
        long_result["candidate_entry"]
        == 106.5
    )

    print("\n=== SHORT SETUP ===")

    short_setup = {
        "setup_status": "valid_setup",
        "direction": "bearish",
        "order_block": {
            "direction": "bearish",
            "low": 200.0,
            "high": 210.0,
        },
        "fvg": {
            "direction": "bearish",
            "gap_low": 202.0,
            "gap_high": 205.0,
        },
    }

    short_result = engine.generate(
        short_setup
    )

    print(short_result)

    assert short_result["approved"] is True
    assert (
        short_result["status"]
        == "ENTRY_ZONE_READY"
    )
    assert (
        short_result["direction"]
        == "short"
    )
    assert (
        short_result["entry_zone_low"]
        == 202.0
    )
    assert (
        short_result["entry_zone_high"]
        == 205.0
    )
    assert (
        short_result["candidate_entry"]
        == 203.5
    )

    print("\n=== INVALID SETUP TEST ===")

    invalid_setup = {
        "setup_status": "incomplete_setup",
        "direction": "bullish",
        "order_block": {
            "direction": "bullish",
            "low": 100.0,
            "high": 110.0,
        },
    }

    invalid_result = engine.generate(
        invalid_setup
    )

    print(invalid_result)

    assert (
        invalid_result["approved"]
        is False
    )
    assert (
        invalid_result["status"]
        == "NO_TRADE"
    )
    assert (
        invalid_result["reason"]
        == "setup_not_valid"
    )

    print(
        "\nALL SMC ENTRY MODEL TESTS PASSED"
    )


if __name__ == "__main__":
    test_entry_model()