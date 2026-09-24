import pytest

from execution.exchange import BybitExchange


def test_exchange_defaults_to_testnet_without_credentials():
    exchange = BybitExchange()

    assert exchange.base_url == "https://api-testnet.bybit.com"


def test_exchange_rejects_missing_credentials():
    exchange = BybitExchange()

    with pytest.raises(
        RuntimeError,
        match="Bybit API credentials are not configured",
    ):
        exchange.get_positions()


def test_sign_get_produces_expected_hmac():
    exchange = BybitExchange()

    exchange.api_key = "test_api_key"
    exchange.api_secret = "test_api_secret"
    exchange.recv_window = 5000

    signature = exchange._sign_get(
        "1672531200000",
        "accountType=UNIFIED&coin=USDT",
    )

    assert signature == (
        "46c8e5c42cf4e2fe508d60efd422184658262d54210fe658da40dae75ddba25e"
    )



def test_get_server_time_returns_bybit_time():
    exchange = BybitExchange()
    result = exchange.get_server_time()
    assert "timeSecond" in result
    assert "timeNano" in result



def test_get_instrument_info_returns_trading_rules():
    exchange = BybitExchange()
    result = exchange.get_instrument_info("BTCUSDT")
    assert len(result) >= 1
    instrument = result[0]
    assert instrument["symbol"] == "BTCUSDT"
    assert instrument["status"] == "Trading"
    assert instrument["priceFilter"]["tickSize"] == "0.10"
    assert instrument["lotSizeFilter"]["qtyStep"] == "0.001"
    assert instrument["lotSizeFilter"]["minOrderQty"] == "0.001"


def test_order_engine_normalizes_quantity_to_exchange_step():
    from execution.order_engine import OrderEngine

    class FakeExchange:
        def get_instrument_info(self, symbol):
            return [{
                "symbol": symbol,
                "lotSizeFilter": {
                    "qtyStep": "0.001",
                    "minOrderQty": "0.001",
                },
            }]

    engine = OrderEngine(FakeExchange())

    assert engine.normalize_quantity("BTCUSDT", "0.003742") == "0.003"


def test_order_engine_normalizes_price_to_exchange_tick():
    from execution.order_engine import OrderEngine

    class FakeExchange:
        def get_instrument_info(self, symbol):
            return [{
                "symbol": symbol,
                "priceFilter": {
                    "tickSize": "0.10",
                    "minPrice": "0.10",
                    "maxPrice": "1999999.80",
                },
            }]

    engine = OrderEngine(FakeExchange())

    assert engine.normalize_price("BTCUSDT", "86854.137") == "86854.10"

def test_order_engine_validates_max_quantity():
    from execution.order_engine import OrderEngine

    class FakeExchange:
        def get_instrument_info(self, symbol):
            return [{
                "symbol": symbol,
                "priceFilter": {
                    "tickSize": "0.10",
                    "minPrice": "0.10",
                    "maxPrice": "1999999.80",
                },
                "lotSizeFilter": {
                    "qtyStep": "0.001",
                    "minOrderQty": "0.001",
                    "maxOrderQty": "1.000",
                    "minNotionalValue": "5",
                },
            }]

    engine = OrderEngine(FakeExchange())

    assert engine.validate_max_quantity("BTCUSDT", "0.742") == "0.742"

    with pytest.raises(ValueError, match="exceeds maximum quantity"):
        engine.validate_max_quantity("BTCUSDT", "1.001")

def test_order_engine_validates_price_range():
    from execution.order_engine import OrderEngine

    class FakeExchange:
        def get_instrument_info(self, symbol):
            return [{
                "symbol": symbol,
                "priceFilter": {
                    "tickSize": "0.10",
                    "minPrice": "100.00",
                    "maxPrice": "100000.00",
                },
                "lotSizeFilter": {
                    "qtyStep": "0.001",
                    "minOrderQty": "0.001",
                    "maxOrderQty": "10.000",
                    "minNotionalValue": "5",
                },
            }]

    engine = OrderEngine(FakeExchange())

    assert engine.validate_price_range("BTCUSDT", "86854.137") == "86854.10"

    with pytest.raises(ValueError, match="below minimum price"):
        engine.validate_price_range("BTCUSDT", "99.95")

    with pytest.raises(ValueError, match="exceeds maximum price"):
        engine.validate_price_range("BTCUSDT", "100000.10")

def test_order_engine_prepares_guardian_approved_quantity():
    from execution.order_engine import OrderEngine

    class FakeExchange:
        def get_instrument_info(self, symbol):
            return [{
                "symbol": symbol,
                "lotSizeFilter": {
                    "qtyStep": "0.001",
                    "minOrderQty": "0.001",
                    "maxOrderQty": "10.000",
                    "minNotionalValue": "5",
                },
                "priceFilter": {
                    "tickSize": "0.10",
                    "minPrice": "0.10",
                    "maxPrice": "1999999.80",
                },
            }]

    engine = OrderEngine(FakeExchange())

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
        "position_size": "0.003742",
    }

    assert engine.prepare_quantity(
        "BTCUSDT",
        trade_plan,
    ) == "0.003"

    with pytest.raises(ValueError, match="GUARDIAN_APPROVED"):
        engine.prepare_quantity(
            "BTCUSDT",
            {
                "status": "NO_TRADE",
                "position_size": "0.003742",
            },
        )

    with pytest.raises(ValueError, match="missing position_size"):
        engine.prepare_quantity(
            "BTCUSDT",
            {
                "status": "GUARDIAN_APPROVED",
            },
        )

def test_order_engine_prepares_guardian_approved_prices():
    from execution.order_engine import OrderEngine

    class FakeExchange:
        def get_instrument_info(self, symbol):
            return [{
                "symbol": symbol,
                "priceFilter": {
                    "tickSize": "0.10",
                    "minPrice": "0.10",
                    "maxPrice": "1999999.80",
                },
                "lotSizeFilter": {
                    "qtyStep": "0.001",
                    "minOrderQty": "0.001",
                    "maxOrderQty": "10.000",
                    "minNotionalValue": "5",
                },
            }]

    engine = OrderEngine(FakeExchange())

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
        "entry_price": "86854.137",
        "stop_loss": "86001.234",
        "take_profit": "88555.678",
    }

    assert engine.prepare_prices(
        "BTCUSDT",
        trade_plan,
    ) == {
        "entry_price": "86854.10",
        "stop_loss": "86001.20",
        "take_profit": "88555.60",
    }

    with pytest.raises(ValueError, match="missing"):
        engine.prepare_prices(
            "BTCUSDT",
            {
                "status": "GUARDIAN_APPROVED",
                "entry_price": "86854.137",
                "stop_loss": "86001.234",
            },
        )

def test_order_engine_prepares_complete_guardian_order():
    from execution.order_engine import OrderEngine

    class FakeExchange:
        def get_instrument_info(self, symbol):
            return [{
                "symbol": symbol,
                "priceFilter": {
                    "tickSize": "0.10",
                    "minPrice": "0.10",
                    "maxPrice": "1999999.80",
                },
                "lotSizeFilter": {
                    "qtyStep": "0.001",
                    "minOrderQty": "0.001",
                    "maxOrderQty": "10.000",
                    "minNotionalValue": "5",
                },
            }]

    engine = OrderEngine(FakeExchange())

    trade_plan = {
        "status": "GUARDIAN_APPROVED",
        "direction": "long",
        "position_size": "0.003742",
        "entry_price": "86854.137",
        "stop_loss": "86001.234",
        "take_profit": "88555.678",
    }

    assert engine.prepare_order(
        "BTCUSDT",
        trade_plan,
    ) == {
        "category": "linear",
        "symbol": "BTCUSDT",
        "side": "Buy",
        "orderType": "Limit",
        "qty": "0.003",
        "price": "86854.10",
        "stopLoss": "86001.20",
        "takeProfit": "88555.60",
    }

    short_plan = {
        **trade_plan,
        "direction": "short",
        "stop_loss": "88555.678",
        "take_profit": "85000.123",
    }

    assert engine.prepare_order(
        "BTCUSDT",
        short_plan,
    )["side"] == "Sell"

def test_order_engine_validates_final_order_geometry():
    from execution.order_engine import OrderEngine

    engine = OrderEngine(None)

    assert engine.validate_order_geometry(
        "Buy",
        "86854.10",
        "86001.20",
        "88555.60",
    ) is True

    assert engine.validate_order_geometry(
        "Sell",
        "86854.10",
        "88555.60",
        "85000.10",
    ) is True

    with pytest.raises(ValueError, match="Invalid Buy order geometry"):
        engine.validate_order_geometry(
            "Buy",
            "86854.10",
            "87000.00",
            "88555.60",
        )

    with pytest.raises(ValueError, match="Invalid Sell order geometry"):
        engine.validate_order_geometry(
            "Sell",
            "86854.10",
            "85000.00",
            "88555.60",
        )

    with pytest.raises(ValueError, match="Unsupported order side"):
        engine.validate_order_geometry(
            "Invalid",
            "86854.10",
            "86001.20",
            "88555.60",
        )

def test_order_engine_prepares_reduce_only_protection_orders():
    from execution.order_engine import OrderEngine

    class FakeExchange:
        def get_instrument_info(self, symbol):
            return [{
                "symbol": symbol,
                "priceFilter": {
                    "tickSize": "0.10",
                    "minPrice": "0.10",
                    "maxPrice": "1999999.80",
                },
                "lotSizeFilter": {
                    "qtyStep": "0.001",
                    "minOrderQty": "0.001",
                    "maxOrderQty": "10.000",
                    "minNotionalValue": "5",
                },
            }]

    engine = OrderEngine(FakeExchange())

    long_plan = {
        "status": "GUARDIAN_APPROVED",
        "direction": "long",
        "position_size": "0.003742",
        "entry_price": "86854.137",
        "stop_loss": "86001.234",
        "take_profit": "88555.678",
    }

    result = engine.prepare_protection_orders(
        "BTCUSDT",
        long_plan,
    )

    assert result == {
        "category": "linear",
        "symbol": "BTCUSDT",
        "tpslMode": "Full",
        "positionIdx": 0,
        "stopLoss": "86001.20",
        "takeProfit": "88555.60",
        "slTriggerBy": "MarkPrice",
        "tpTriggerBy": "MarkPrice",
    }

    short_plan = {
        **long_plan,
        "direction": "short",
        "stop_loss": "88555.678",
        "take_profit": "85000.123",
    }

    result = engine.prepare_protection_orders(
        "BTCUSDT",
        short_plan,
    )

    assert result["tpslMode"] == "Full"
    assert result["positionIdx"] == 0
    assert result["stopLoss"] == "88555.60"
    assert result["takeProfit"] == "85000.10"
    assert result["slTriggerBy"] == "MarkPrice"
    assert result["tpTriggerBy"] == "MarkPrice"

def test_authenticated_post_builds_signed_request_without_network():
    from execution.exchange import BybitExchange

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "retCode": 0,
                "retMsg": "OK",
                "result": {},
            }

    captured = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse()

    exchange = BybitExchange()
    exchange.api_key = "test_api_key"
    exchange.api_secret = "test_api_secret"
    exchange.recv_window = 5000
    exchange.base_url = "https://api-testnet.bybit.com"

    import execution.exchange as exchange_module
    original_post = exchange_module.requests.post
    original_time = exchange_module.time.time

    exchange_module.requests.post = fake_post
    exchange_module.time.time = lambda: 1750000000.0

    try:
        result = exchange._authenticated_post(
            "/v5/position/trading-stop",
            {
                "category": "linear",
                "symbol": "BTCUSDT",
                "tpslMode": "Full",
                "positionIdx": 0,
                "stopLoss": "86001.20",
                "takeProfit": "88555.60",
            },
        )
    finally:
        exchange_module.requests.post = original_post
        exchange_module.time.time = original_time

    assert result["retCode"] == 0
    assert captured["url"] == (
        "https://api-testnet.bybit.com"
        "/v5/position/trading-stop"
    )
    assert captured["timeout"] == 10
    assert captured["data"] == (
        '{"category":"linear","symbol":"BTCUSDT",'
        '"tpslMode":"Full","positionIdx":0,'
        '"stopLoss":"86001.20","takeProfit":"88555.60"}'
    )

    assert captured["headers"]["X-BAPI-API-KEY"] == "test_api_key"
    assert captured["headers"]["X-BAPI-TIMESTAMP"] == "1750000000000"
    assert captured["headers"]["X-BAPI-RECV-WINDOW"] == "5000"
    assert len(captured["headers"]["X-BAPI-SIGN"]) == 64
    assert captured["headers"]["Content-Type"] == "application/json"

def test_set_trading_stop_calls_trading_stop_endpoint():
    from execution.exchange import BybitExchange

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "retCode": 0,
                "retMsg": "OK",
                "result": {},
            }

    def fake_post(url, data=None, headers=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse()

    exchange = BybitExchange()
    exchange.api_key = "test_api_key"
    exchange.api_secret = "test_api_secret"
    exchange.recv_window = 5000
    exchange.base_url = "https://api-testnet.bybit.com"

    import execution.exchange as exchange_module

    original_post = exchange_module.requests.post
    original_time = exchange_module.time.time

    exchange_module.requests.post = fake_post
    exchange_module.time.time = lambda: 1750000000.0

    try:
        result = exchange.set_trading_stop(
            symbol="BTCUSDT",
            stop_loss="86001.20",
            take_profit="88555.60",
        )
    finally:
        exchange_module.requests.post = original_post
        exchange_module.time.time = original_time

    assert result["retCode"] == 0

    assert captured["url"] == (
        "https://api-testnet.bybit.com"
        "/v5/position/trading-stop"
    )

    assert captured["data"] == (
        '{"category":"linear","symbol":"BTCUSDT",'
        '"tpslMode":"Full","positionIdx":0,'
        '"stopLoss":"86001.20","takeProfit":"88555.60",'
        '"slTriggerBy":"MarkPrice","tpTriggerBy":"MarkPrice"}'
    )

    assert captured["headers"]["X-BAPI-API-KEY"] == "test_api_key"
    assert captured["headers"]["X-BAPI-TIMESTAMP"] == "1750000000000"
    assert captured["headers"]["X-BAPI-RECV-WINDOW"] == "5000"
    assert len(captured["headers"]["X-BAPI-SIGN"]) == 64
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["timeout"] == 10

def test_get_position_returns_active_position():
    from execution.exchange import BybitExchange

    exchange = BybitExchange()

    exchange.get_positions = lambda symbol: [
        {"symbol": "BTCUSDT", "size": "0"},
        {"symbol": "BTCUSDT", "size": "0.003"},
    ]

    result = exchange.get_position("BTCUSDT")

    assert result == {
        "symbol": "BTCUSDT",
        "size": "0.003",
    }


def test_get_position_returns_none_when_no_active_position():
    from execution.exchange import BybitExchange

    exchange = BybitExchange()

    exchange.get_positions = lambda symbol: [
        {"symbol": "BTCUSDT", "size": "0"},
        {"symbol": "BTCUSDT", "size": "0.000"},
    ]

    result = exchange.get_position("BTCUSDT")

    assert result is None


def test_get_position_ignores_malformed_position_size():
    from execution.exchange import BybitExchange

    exchange = BybitExchange()

    exchange.get_positions = lambda symbol: [
        {"symbol": "BTCUSDT", "size": "invalid"},
        {"symbol": "BTCUSDT", "size": "0.005"},
    ]

    result = exchange.get_position("BTCUSDT")

    assert result == {
        "symbol": "BTCUSDT",
        "size": "0.005",
    }

def test_create_order_blocks_trading_when_disabled(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings.settings, "TRADING_ENABLED", False)

    exchange = BybitExchange()

    with pytest.raises(
        RuntimeError,
        match="Trading is disabled",
    ):
        exchange.create_order(
            symbol="BTCUSDT",
            side="Buy",
            order_type="Limit",
            qty="0.003",
            price="86854.10",
        )


def test_create_order_rejects_invalid_side(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings.settings, "TRADING_ENABLED", True)

    exchange = BybitExchange()

    with pytest.raises(ValueError, match="Side must be Buy or Sell"):
        exchange.create_order(
            symbol="BTCUSDT",
            side="Invalid",
            order_type="Limit",
            qty="0.003",
            price="86854.10",
        )


def test_create_order_rejects_non_limit_order(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings.settings, "TRADING_ENABLED", True)

    exchange = BybitExchange()

    with pytest.raises(
        ValueError,
        match="Only Limit orders are supported",
    ):
        exchange.create_order(
            symbol="BTCUSDT",
            side="Buy",
            order_type="Market",
            qty="0.003",
            price="86854.10",
        )


def test_create_order_requires_limit_price(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings.settings, "TRADING_ENABLED", True)

    exchange = BybitExchange()

    with pytest.raises(
        ValueError,
        match="Limit orders require a price",
    ):
        exchange.create_order(
            symbol="BTCUSDT",
            side="Buy",
            order_type="Limit",
            qty="0.003",
        )


def test_create_order_builds_expected_payload(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings.settings, "TRADING_ENABLED", True)

    exchange = BybitExchange()

    captured = {}

    def fake_authenticated_post(path, body):
        captured["path"] = path
        captured["body"] = body
        return {"retCode": 0}

    monkeypatch.setattr(
        exchange,
        "_authenticated_post",
        fake_authenticated_post,
    )

    result = exchange.create_order(
        symbol="btcusdt",
        side="Buy",
        order_type="Limit",
        qty="0.003",
        price="86854.10",
    )

    assert result == {"retCode": 0}

    assert captured["path"] == "/v5/order/create"

    assert captured["body"] == {
        "category": "linear",
        "symbol": "BTCUSDT",
        "side": "Buy",
        "orderType": "Limit",
        "qty": "0.003",
        "price": "86854.10",
        "timeInForce": "GTC",
        "positionIdx": 0,
    }


def test_get_order_returns_matching_order():
    exchange = BybitExchange()

    def fake_authenticated_get(path, params):
        assert path == "/v5/order/realtime"
        assert params == {
            "category": "linear",
            "symbol": "BTCUSDT",
            "orderId": "ORDER-123",
        }
        return {
            "result": {
                "list": [
                    {
                        "orderId": "ORDER-123",
                        "orderStatus": "Filled",
                        "side": "Buy",
                    }
                ]
            }
        }

    exchange._authenticated_get = fake_authenticated_get

    result = exchange.get_order("BTCUSDT", "ORDER-123")

    assert result["orderId"] == "ORDER-123"
    assert result["orderStatus"] == "Filled"


def test_get_order_returns_none_when_order_is_missing():
    exchange = BybitExchange()

    exchange._authenticated_get = lambda path, params: {
        "result": {
            "list": []
        }
    }

    result = exchange.get_order("BTCUSDT", "MISSING-ORDER")

    assert result is None
