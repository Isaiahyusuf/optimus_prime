import pytest

from execution.trade_record import TradeRecord


def test_trade_record_starts_created():
    record = TradeRecord("btcusdt")

    assert record.snapshot() == {
        "symbol": "BTCUSDT",
        "order_id": None,
        "state": "CREATED",
        "order_quantity": None,
        "filled_quantity": None,
        "remaining_quantity": None,
        "average_fill_price": None,
    }


def test_trade_record_accepts_order_id():
    record = TradeRecord(
        "btcusdt",
        order_id="ORDER-123",
    )

    assert record.order_id == "ORDER-123"
    assert record.state == "CREATED"


def test_trade_record_updates_state():
    record = TradeRecord("BTCUSDT")

    record.update_state("ENTRY_SUBMITTED")

    assert record.state == "ENTRY_SUBMITTED"


def test_trade_record_rejects_invalid_state():
    record = TradeRecord("BTCUSDT")

    with pytest.raises(
        ValueError,
        match="Invalid trade record state",
    ):
        record.update_state("INVALID")


def test_trade_record_updates_execution_data():
    record = TradeRecord(
        "BTCUSDT",
        order_id="ORDER-123",
    )

    record.update_execution(
        order_quantity=0.003,
        filled_quantity=0.001,
        remaining_quantity=0.002,
        average_fill_price=86854.10,
    )

    assert record.snapshot() == {
        "symbol": "BTCUSDT",
        "order_id": "ORDER-123",
        "state": "CREATED",
        "order_quantity": 0.003,
        "filled_quantity": 0.001,
        "remaining_quantity": 0.002,
        "average_fill_price": 86854.10,
    }


def test_trade_record_rejects_missing_symbol():
    with pytest.raises(ValueError, match="Symbol is required"):
        TradeRecord("")


def test_trade_record_rejects_invalid_initial_state():
    with pytest.raises(
        ValueError,
        match="Invalid trade record state",
    ):
        TradeRecord(
            "BTCUSDT",
            state="INVALID",
        )


def test_trade_record_accepts_position_verification_failed_state():
    record = TradeRecord(
        "BTCUSDT",
        state="POSITION_VERIFICATION_FAILED",
    )

    assert record.state == "POSITION_VERIFICATION_FAILED"


def test_trade_record_accepts_entry_cancellation_failed_state():
    record = TradeRecord(
        symbol="BTCUSDT",
        order_id="TEST-CANCEL-FAIL",
    )

    record.update_state("ENTRY_CANCELLATION_FAILED")

    assert record.snapshot()["state"] == "ENTRY_CANCELLATION_FAILED"
