import pytest

from execution.order_lifecycle import OrderLifecycle


def test_new_order_maps_to_entry_pending():
    lifecycle = OrderLifecycle()

    assert lifecycle.interpret(
        {"orderStatus": "New"}
    ) == "ENTRY_PENDING"


def test_partially_filled_order_maps_to_entry_partial():
    lifecycle = OrderLifecycle()

    assert lifecycle.interpret(
        {"orderStatus": "PartiallyFilled"}
    ) == "ENTRY_PARTIALLY_FILLED"


def test_filled_order_maps_to_entry_filled():
    lifecycle = OrderLifecycle()

    assert lifecycle.interpret(
        {"orderStatus": "Filled"}
    ) == "ENTRY_FILLED"


def test_cancelled_order_maps_to_entry_cancelled():
    lifecycle = OrderLifecycle()

    assert lifecycle.interpret(
        {"orderStatus": "Cancelled"}
    ) == "ENTRY_CANCELLED"


def test_rejected_order_maps_to_entry_rejected():
    lifecycle = OrderLifecycle()

    assert lifecycle.interpret(
        {"orderStatus": "Rejected"}
    ) == "ENTRY_REJECTED"


def test_unknown_order_maps_to_unknown_entry_state():
    lifecycle = OrderLifecycle()

    assert lifecycle.interpret(
        {"orderStatus": "SomethingUnexpected"}
    ) == "ENTRY_STATE_UNKNOWN"


def test_lifecycle_preserves_execution_data():
    lifecycle = OrderLifecycle()

    result = lifecycle.interpret_with_execution(
        {
            "orderStatus": "PartiallyFilled",
            "qty": "0.003",
            "cumExecQty": "0.001",
            "leavesQty": "0.002",
            "avgPrice": "86854.10",
        }
    )

    assert result == {
        "state": "ENTRY_PARTIALLY_FILLED",
        "execution": {
            "order_quantity": 0.003,
            "filled_quantity": 0.001,
            "remaining_quantity": 0.002,
            "average_fill_price": 86854.10,
        },
    }


def test_lifecycle_rejects_invalid_order():
    lifecycle = OrderLifecycle()

    with pytest.raises(
        ValueError,
        match="Order must be a dictionary",
    ):
        lifecycle.interpret(None)


def test_filled_order_requires_full_execution():
    lifecycle = OrderLifecycle()

    with pytest.raises(
        ValueError,
        match="Filled order execution data is inconsistent",
    ):
        lifecycle.interpret_with_execution(
            {
                "orderStatus": "Filled",
                "qty": "0.003",
                "cumExecQty": "0.002",
                "leavesQty": "0.001",
                "avgPrice": "86854.10",
            }
        )


def test_partially_filled_order_requires_partial_execution():
    lifecycle = OrderLifecycle()

    with pytest.raises(
        ValueError,
        match="Partially filled order execution data is inconsistent",
    ):
        lifecycle.interpret_with_execution(
            {
                "orderStatus": "PartiallyFilled",
                "qty": "0.003",
                "cumExecQty": "0.003",
                "leavesQty": "0",
                "avgPrice": "86854.10",
            }
        )


def test_pending_order_cannot_have_filled_quantity():
    lifecycle = OrderLifecycle()

    with pytest.raises(
        ValueError,
        match="Pending order execution data is inconsistent",
    ):
        lifecycle.interpret_with_execution(
            {
                "orderStatus": "New",
                "qty": "0.003",
                "cumExecQty": "0.001",
                "leavesQty": "0.002",
                "avgPrice": "86854.10",
            }
        )


def test_lifecycle_rejects_inconsistent_execution_quantities():
    lifecycle = OrderLifecycle()

    with pytest.raises(
        ValueError,
        match="Execution quantities are inconsistent",
    ):
        lifecycle.interpret_with_execution(
            {
                "orderStatus": "PartiallyFilled",
                "qty": "0.003",
                "cumExecQty": "0.002",
                "leavesQty": "0.002",
                "avgPrice": "86854.10",
            }
        )
