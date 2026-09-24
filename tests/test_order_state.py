import pytest

from execution.order_state import OrderState


def test_new_order_is_pending():
    state = OrderState()
    assert state.interpret({"orderStatus": "New"}) == "PENDING"


def test_partially_filled_order_is_partial():
    state = OrderState()
    assert state.interpret({"orderStatus": "PartiallyFilled"}) == "PARTIALLY_FILLED"


def test_filled_order_is_filled():
    state = OrderState()
    assert state.interpret({"orderStatus": "Filled"}) == "FILLED"


def test_cancelled_order_is_cancelled():
    state = OrderState()
    assert state.interpret({"orderStatus": "Cancelled"}) == "CANCELLED"


def test_rejected_order_is_rejected():
    state = OrderState()
    assert state.interpret({"orderStatus": "Rejected"}) == "REJECTED"


def test_unknown_order_status_is_unknown():
    state = OrderState()
    assert state.interpret({"orderStatus": "SomethingUnexpected"}) == "UNKNOWN"


def test_missing_order_status_is_rejected():
    state = OrderState()

    with pytest.raises(ValueError, match="Order status is required"):
        state.interpret({})


def test_non_dictionary_order_is_rejected():
    state = OrderState()

    with pytest.raises(ValueError, match="Order must be a dictionary"):
        state.interpret(None)

def test_get_execution_data_returns_order_quantities():
    order_state = OrderState()

    result = order_state.get_execution_data(
        {
            "qty": "0.003",
            "cumExecQty": "0.001",
            "leavesQty": "0.002",
            "avgPrice": "86854.10",
        }
    )

    assert result == {
        "order_quantity": 0.003,
        "filled_quantity": 0.001,
        "remaining_quantity": 0.002,
        "average_fill_price": 86854.10,
    }

def test_get_execution_data_rejects_missing_quantity():
    order_state = OrderState()

    with pytest.raises(ValueError, match="Order quantity is required"):
        order_state.get_execution_data(
            {
                "cumExecQty": "0.001",
                "leavesQty": "0.002",
                "avgPrice": "86854.10",
            }
        )


def test_get_execution_data_rejects_non_numeric_values():
    order_state = OrderState()

    with pytest.raises(ValueError, match="Order quantity must be numeric"):
        order_state.get_execution_data(
            {
                "qty": "invalid",
                "cumExecQty": "0.001",
                "leavesQty": "0.002",
                "avgPrice": "86854.10",
            }
        )


def test_get_execution_data_rejects_negative_values():
    order_state = OrderState()

    with pytest.raises(
        ValueError,
        match="Cumulative executed quantity cannot be negative",
    ):
        order_state.get_execution_data(
            {
                "qty": "0.003",
                "cumExecQty": "-0.001",
                "leavesQty": "0.002",
                "avgPrice": "86854.10",
            }
        )

def test_get_execution_data_rejects_missing_quantity():
    order_state = OrderState()

    with pytest.raises(ValueError, match="Order quantity is required"):
        order_state.get_execution_data(
            {
                "cumExecQty": "0.001",
                "leavesQty": "0.002",
                "avgPrice": "86854.10",
            }
        )


def test_get_execution_data_rejects_non_numeric_values():
    order_state = OrderState()

    with pytest.raises(ValueError, match="Order quantity must be numeric"):
        order_state.get_execution_data(
            {
                "qty": "invalid",
                "cumExecQty": "0.001",
                "leavesQty": "0.002",
                "avgPrice": "86854.10",
            }
        )


def test_get_execution_data_rejects_negative_values():
    order_state = OrderState()

    with pytest.raises(
        ValueError,
        match="Cumulative executed quantity cannot be negative",
    ):
        order_state.get_execution_data(
            {
                "qty": "0.003",
                "cumExecQty": "-0.001",
                "leavesQty": "0.002",
                "avgPrice": "86854.10",
            }
        )
