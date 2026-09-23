from risk.risk_manager import RiskManager


def test_risk_manager():
    manager = RiskManager(
        risk_per_trade=0.01,
        min_risk_reward=2.0,
        max_position_value_pct=100.0,
        max_leverage=10.0,
    )

    account_equity = 1000.0
    entry_price = 100.0
    stop_loss = 95.0
    take_profit = 110.0

    result = manager.evaluate_trade_risk(
        account_equity,
        entry_price,
        stop_loss,
        take_profit,
    )

    assert result["approved"] is True
    assert result["reason"] == "risk_approved"

    assert result["risk_amount"] == 10.0
    assert result["position_size"] == 2.0
    assert result["position_value"] == 200.0
    assert result["stop_distance"] == 5.0
    assert result["stop_distance_pct"] == 0.05
    assert result["risk_reward"] == 2.0

    assert (
        result["position_value"]
        <= result["maximum_position_value"]
    )

    assert (
        result["effective_leverage"]
        <= result["max_leverage"]
    )