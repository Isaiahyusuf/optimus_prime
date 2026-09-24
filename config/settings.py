import os


class Settings:
    """Application configuration loaded from environment variables."""

    BYBIT_API_KEY = os.getenv("BYBIT_API_KEY", "")
    BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET", "")

    BYBIT_TESTNET = os.getenv("BYBIT_TESTNET", "true").lower() == "true"
    BYBIT_RECV_WINDOW = int(os.getenv("BYBIT_RECV_WINDOW", "5000"))

    TRADING_ENABLED = os.getenv("TRADING_ENABLED", "false").lower() == "true"


settings = Settings()
