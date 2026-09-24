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
