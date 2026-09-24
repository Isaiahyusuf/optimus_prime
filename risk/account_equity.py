class AccountEquity:
    """
    Extracts and validates account-level equity from the exchange response.

    This layer does not place or modify trades.
    """

    def __init__(self, exchange):
        self.exchange = exchange

    def get_equity(self, coin: str = "USDT") -> float:
        if not coin:
            raise ValueError("Coin is required.")

        data = self.exchange.get_wallet_balance(coin.upper())

        if not isinstance(data, dict):
            raise ValueError("Wallet balance response must be a dictionary.")

        raw_equity = data.get("totalEquity")

        if raw_equity is None:
            raise ValueError("Account-level totalEquity is missing.")

        try:
            equity = float(raw_equity)
        except (TypeError, ValueError):
            raise ValueError("Account-level totalEquity must be numeric.")

        if equity <= 0:
            raise ValueError("Account equity must be greater than zero.")

        return equity
