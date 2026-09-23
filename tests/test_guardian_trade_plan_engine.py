from risk.guardian_trade_plan import GuardianTradePlanEngine


def build_guardian_setup():
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
            "price": 104.0,
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


def build_causal_liquidity():
    return [
        {
            "type": "buy_side",
            "subtype": "swing_high",
            "price": 116.5,
            "index": 28,
            "confirmed_at_index": 28,
        },
        {
            "type": "buy_side",
            "subtype": "swing_high",
            "price": 120.0,
            "index": 29,
            "confirmed_at_index": 29,
        },
        {
            "type": "sell_side",
            "subtype": "swing_low",
            "price": 98.0,
            "index": 25,
            "confirmed_at_index": 25,
        },
    ]


def test_guardian_trade_plan_engine_approves_valid_setup():
    engine = GuardianTradePlanEngine()

    result = engine.generate(
        setup=build_guardian_setup(),
        liquidity_levels=build_causal_liquidity(),
        account_equity=1000.0,
    )

    assert result["approved"] is True
    assert result["status"] == "GUARDIAN_APPROVED"
    assert result["reason"] == "guardian_trade_plan_approved"

    assert result["direction"] == "long"
    assert result["entry_price"] == 106.5
    assert result["stop_loss"] == 99.94675
    assert result["take_profit"] == 120.0

    assert result["risk_reward"] == 2.060046541792239
    assert result["risk_amount"] == 10.0

    assert result["position_size"] > 0
    assert result["position_value"] > 0
    assert result["effective_leverage"] > 0


def test_guardian_trade_plan_engine_rejects_invalid_setup():
    engine = GuardianTradePlanEngine()

    result = engine.generate(
        setup={
            "setup_status": "invalid_setup",
        },
        liquidity_levels=build_causal_liquidity(),
        account_equity=1000.0,
    )

    assert result["approved"] is False
    assert result["status"] == "NO_TRADE"
    assert result["reason"] == "setup_not_valid"
    assert result["failed_stage"] == "setup"


def test_guardian_trade_plan_engine_rejects_invalid_account_equity():
    engine = GuardianTradePlanEngine()

    result = engine.generate(
        setup=build_guardian_setup(),
        liquidity_levels=build_causal_liquidity(),
        account_equity=0,
    )

    assert result["approved"] is False
    assert result["status"] == "NO_TRADE"
    assert result["reason"] == "invalid_account_equity"
    assert result["failed_stage"] == "risk_management"


def test_guardian_trade_plan_engine_rejects_invalid_liquidity():
    engine = GuardianTradePlanEngine()

    result = engine.generate(
        setup=build_guardian_setup(),
        liquidity_levels=None,
        account_equity=1000.0,
    )

    assert result["approved"] is False
    assert result["status"] == "NO_TRADE"
    assert result["reason"] == "invalid_liquidity_levels"
    assert result["failed_stage"] == "target_selection"