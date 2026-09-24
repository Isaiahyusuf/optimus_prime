import pytest

from risk.account_equity import AccountEquity


class FakeExchange:
    def __init__(self, response):
        self.response = response
        self.requested_coin = None

    def get_wallet_balance(self, coin):
        self.requested_coin = coin
        return self.response


def test_get_equity_returns_account_total_equity():
    exchange = FakeExchange({"totalEquity": "1000.50"})
    account = AccountEquity(exchange)

    assert account.get_equity("USDT") == 1000.5
    assert exchange.requested_coin == "USDT"


def test_get_equity_rejects_missing_total_equity():
    exchange = FakeExchange({})
    account = AccountEquity(exchange)

    with pytest.raises(ValueError, match="totalEquity is missing"):
        account.get_equity("USDT")


def test_get_equity_rejects_non_numeric_equity():
    exchange = FakeExchange({"totalEquity": "invalid"})
    account = AccountEquity(exchange)

    with pytest.raises(ValueError, match="totalEquity must be numeric"):
        account.get_equity("USDT")


def test_get_equity_rejects_zero_equity():
    exchange = FakeExchange({"totalEquity": "0"})
    account = AccountEquity(exchange)

    with pytest.raises(ValueError, match="greater than zero"):
        account.get_equity("USDT")


def test_get_equity_rejects_negative_equity():
    exchange = FakeExchange({"totalEquity": "-100"})
    account = AccountEquity(exchange)

    with pytest.raises(ValueError, match="greater than zero"):
        account.get_equity("USDT")


def test_get_equity_rejects_invalid_response():
    exchange = FakeExchange(None)
    account = AccountEquity(exchange)

    with pytest.raises(ValueError, match="must be a dictionary"):
        account.get_equity("USDT")


def test_get_equity_requires_coin():
    exchange = FakeExchange({"totalEquity": "1000"})
    account = AccountEquity(exchange)

    with pytest.raises(ValueError, match="Coin is required"):
        account.get_equity("")
