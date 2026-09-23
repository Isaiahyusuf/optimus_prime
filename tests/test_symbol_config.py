from config.symbols import SymbolConfig


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_symbol_config_filters_linear_perpetuals(monkeypatch):
    payload = {
        "retCode": 0,
        "retMsg": "OK",
        "result": {
            "list": [
                {
                    "symbol": "BTCUSDT",
                    "status": "Trading",
                    "contractType": "LinearPerpetual",
                },
                {
                    "symbol": "ETHUSDT",
                    "status": "Trading",
                    "contractType": "LinearPerpetual",
                },
                {
                    "symbol": "BTCUSD",
                    "status": "Trading",
                    "contractType": "InversePerpetual",
                },
                {
                    "symbol": "OLDUSDT",
                    "status": "Settling",
                    "contractType": "LinearPerpetual",
                },
                {
                    "symbol": "OPTIONUSDT",
                    "status": "Trading",
                    "contractType": "Option",
                },
            ]
        },
    }

    def fake_get(url, params=None, timeout=None):
        assert url.endswith(
            "/v5/market/instruments-info"
        )
        assert params["category"] == "linear"
        assert params["settleCoin"] == "USDT"
        return FakeResponse(payload)

    monkeypatch.setattr(
        "config.symbols.requests.get",
        fake_get,
    )

    config = SymbolConfig()

    symbols = config.get_linear_symbols()

    assert symbols == [
        "BTCUSDT",
        "ETHUSDT",
    ]


def test_symbol_config_removes_exclusions(monkeypatch):
    payload = {
        "retCode": 0,
        "retMsg": "OK",
        "result": {
            "list": [
                {
                    "symbol": "BTCUSDT",
                    "status": "Trading",
                    "contractType": "LinearPerpetual",
                },
                {
                    "symbol": "ETHUSDT",
                    "status": "Trading",
                    "contractType": "LinearPerpetual",
                },
                {
                    "symbol": "SOLUSDT",
                    "status": "Trading",
                    "contractType": "LinearPerpetual",
                },
            ]
        },
    }

    def fake_get(url, params=None, timeout=None):
        return FakeResponse(payload)

    monkeypatch.setattr(
        "config.symbols.requests.get",
        fake_get,
    )

    config = SymbolConfig()

    symbols = config.get_symbols(
        exclusions=[
            "ethusdt",
        ]
    )

    assert symbols == [
        "BTCUSDT",
        "SOLUSDT",
    ]


def test_symbol_config_handles_bybit_error(monkeypatch):
    payload = {
        "retCode": 10001,
        "retMsg": "Test API error",
        "result": {},
    }

    def fake_get(url, params=None, timeout=None):
        return FakeResponse(payload)

    monkeypatch.setattr(
        "config.symbols.requests.get",
        fake_get,
    )

    config = SymbolConfig()

    try:
        config.get_linear_symbols()
        assert False, "Expected RuntimeError"
    except RuntimeError as exc:
        assert "Test API error" in str(exc)
        