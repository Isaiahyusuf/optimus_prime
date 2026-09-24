import hashlib
import hmac
import time
from urllib.parse import urlencode

import requests

from config.settings import settings


class BybitExchange:
    """
    Authenticated Bybit V5 exchange client.

    This layer handles authentication and read-only account/exchange
    state. Order placement will be added only after this foundation
    is tested.
    """

    MAINNET_URL = "https://api.bybit.com"
    TESTNET_URL = "https://api-testnet.bybit.com"

    def __init__(self):
        self.api_key = settings.BYBIT_API_KEY
        self.api_secret = settings.BYBIT_API_SECRET
        self.recv_window = settings.BYBIT_RECV_WINDOW

        self.base_url = (
            self.TESTNET_URL
            if settings.BYBIT_TESTNET
            else self.MAINNET_URL
        )

    def _require_credentials(self):
        if not self.api_key or not self.api_secret:
            raise RuntimeError(
                "Bybit API credentials are not configured."
            )

    def _sign_get(self, timestamp: str, query_string: str) -> str:
        payload = (
            f"{timestamp}"
            f"{self.api_key}"
            f"{self.recv_window}"
            f"{query_string}"
        )

        return hmac.new(
            self.api_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _public_get(
        self,
        path: str,
        params: dict | None = None,
    ) -> dict:
        """Make a read-only request to a public Bybit endpoint."""

        response = requests.get(
            f"{self.base_url}{path}",
            params=params or {},
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        if data.get("retCode") != 0:
            raise RuntimeError(
                f"Bybit API error: {data.get("retMsg", "Unknown error")}"
            )

        return data

    def _authenticated_get(
        self,
        path: str,
        params: dict | None = None,
    ) -> dict:
        self._require_credentials()

        params = params or {}

        query_string = urlencode(
            sorted(params.items()),
        )

        timestamp = str(int(time.time() * 1000))

        signature = self._sign_get(
            timestamp,
            query_string,
        )

        headers = {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": str(self.recv_window),
            "X-BAPI-SIGN": signature,
        }

        response = requests.get(
            f"{self.base_url}{path}",
            params=params,
            headers=headers,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        if data.get("retCode") != 0:
            raise RuntimeError(
                f"Bybit API error: {data.get('retMsg', 'Unknown error')}"
            )

        return data

    def _sign_post(
        self,
        timestamp: str,
        body: str,
    ) -> str:
        payload = (
            f"{timestamp}"
            f"{self.api_key}"
            f"{self.recv_window}"
            f"{body}"
        )

        return hmac.new(
            self.api_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _authenticated_post(
        self,
        path: str,
        body: dict | None = None,
    ) -> dict:
        self._require_credentials()

        body = body or {}

        import json

        body_string = json.dumps(
            body,
            separators=(",", ":"),
        )

        timestamp = str(int(time.time() * 1000))

        signature = self._sign_post(
            timestamp,
            body_string,
        )

        headers = {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": str(self.recv_window),
            "X-BAPI-SIGN": signature,
            "Content-Type": "application/json",
        }

        response = requests.post(
            f"{self.base_url}{path}",
            data=body_string,
            headers=headers,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        if data.get("retCode") != 0:
            raise RuntimeError(
                f"Bybit API error: {data.get('retMsg', 'Unknown error')}"
            )

        return data

    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        qty: str | float,
        price: str | float | None = None,
        position_idx: int = 0,
        time_in_force: str = "GTC",
    ) -> dict:
        """
        Submit an entry order to Bybit.

        Trading is blocked unless TRADING_ENABLED is explicitly enabled.
        This method does not attach TP/SL; protection is handled separately
        through the trading-stop endpoint.
        """

        if not settings.TRADING_ENABLED:
            raise RuntimeError(
                "Trading is disabled. Set TRADING_ENABLED=true to submit orders."
            )

        if not symbol:
            raise ValueError("Symbol is required.")

        if side not in {"Buy", "Sell"}:
            raise ValueError("Side must be Buy or Sell.")

        if order_type != "Limit":
            raise ValueError("Only Limit orders are supported.")

        if position_idx not in {0, 1, 2}:
            raise ValueError("Position index must be 0, 1, or 2.")

        if time_in_force not in {"GTC", "IOC", "FOK"}:
            raise ValueError(
                "Time in force must be GTC, IOC, or FOK."
            )

        if price is None:
            raise ValueError("Limit orders require a price.")

        body = {
            "category": "linear",
            "symbol": symbol.upper(),
            "side": side,
            "orderType": order_type,
            "qty": str(qty),
            "price": str(price),
            "timeInForce": time_in_force,
            "positionIdx": position_idx,
        }

        return self._authenticated_post(
            "/v5/order/create",
            body,
        )

    def set_trading_stop(
        self,
        symbol: str,
        stop_loss: str | float,
        take_profit: str | float,
        position_idx: int = 0,
        tpsl_mode: str = "Full",
        sl_trigger_by: str = "MarkPrice",
        tp_trigger_by: str = "MarkPrice",
    ) -> dict:
        """
        Set TP/SL protection for an existing linear position.

        This method submits to Bybit's Trading Stop endpoint.
        The caller is responsible for ensuring the position exists.
        """

        if not symbol:
            raise ValueError("Symbol is required.")

        if position_idx not in {0, 1, 2}:
            raise ValueError(
                "position_idx must be 0, 1, or 2."
            )

        if tpsl_mode != "Full":
            raise ValueError(
                "Only Full TP/SL mode is currently supported."
            )

        if sl_trigger_by not in {
            "MarkPrice",
            "IndexPrice",
            "LastPrice",
        }:
            raise ValueError(
                f"Unsupported SL trigger type: {sl_trigger_by}"
            )

        if tp_trigger_by not in {
            "MarkPrice",
            "IndexPrice",
            "LastPrice",
        }:
            raise ValueError(
                f"Unsupported TP trigger type: {tp_trigger_by}"
            )

        body = {
            "category": "linear",
            "symbol": symbol.upper(),
            "tpslMode": tpsl_mode,
            "positionIdx": position_idx,
            "stopLoss": str(stop_loss),
            "takeProfit": str(take_profit),
            "slTriggerBy": sl_trigger_by,
            "tpTriggerBy": tp_trigger_by,
        }

        return self._authenticated_post(
            "/v5/position/trading-stop",
            body,
        )

    def get_server_time(self) -> dict:
        """Get the current Bybit server time."""

        response = requests.get(
            f"{self.base_url}/v5/market/time",
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        if data.get("retCode") != 0:
            raise RuntimeError(
                f"Bybit API error: {data.get("retMsg", "Unknown error")}" 
            )

        return data["result"]

    def get_wallet_balance(self, coin: str = "USDT") -> dict:
        """
        Get unified account wallet balance for a coin.
        """

        data = self._authenticated_get(
            "/v5/account/wallet-balance",
            {
                "accountType": "UNIFIED",
                "coin": coin.upper(),
            },
        )

        return data["result"]

    def get_positions(self, symbol: str | None = None) -> list[dict]:
        """
        Get linear futures positions.
        """

        params = {
            "category": "linear",
        }

        if symbol:
            params["symbol"] = symbol.upper()

        data = self._authenticated_get(
            "/v5/position/list",
            params,
        )

        return data.get("result", {}).get("list", [])

    def get_position(
        self,
        symbol: str,
    ) -> dict | None:
        """
        Get the active linear position for a symbol.

        Returns the first non-zero position, or None when no active
        position is reported.
        """

        if not symbol:
            raise ValueError("Symbol is required.")

        positions = self.get_positions(symbol)

        for position in positions:
            size = position.get("size", "0")

            try:
                if float(size) != 0:
                    return position
            except (TypeError, ValueError):
                continue

        return None

    def get_order(
        self,
        symbol: str,
        order_id: str,
    ) -> dict | None:
        """
        Get the current state of a specific linear futures order.

        This method is read-only and never modifies exchange state.
        """

        if not symbol:
            raise ValueError("Symbol is required.")

        if not order_id:
            raise ValueError("Order ID is required.")

        data = self._authenticated_get(
            "/v5/order/realtime",
            {
                "category": "linear",
                "symbol": symbol.upper(),
                "orderId": order_id,
            },
        )

        orders = data.get("result", {}).get("list", [])

        if not orders:
            return None

        return orders[0]

    def get_open_orders(
        self,
        symbol: str | None = None,
    ) -> list[dict]:
        """
        Get open linear futures orders.
        """

        params = {
            "category": "linear",
        }

        if symbol:
            params["symbol"] = symbol.upper()
        else:
            params["settleCoin"] = "USDT"

        data = self._authenticated_get(
            "/v5/order/realtime",
            params,
        )

        return data.get("result", {}).get("list", [])

    def get_instrument_info(
        self,
        symbol: str,
    ) -> list[dict]:
        """
        Get linear futures instrument specifications.
        """

        data = self._public_get(
            "/v5/market/instruments-info",
            {
                "category": "linear",
                "symbol": symbol.upper(),
            },
        )

        return data.get("result", {}).get("list", [])
