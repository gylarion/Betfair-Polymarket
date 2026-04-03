from pydantic_settings import BaseSettings
from pydantic import Field


class BetfairSettings(BaseSettings):
    username: str = ""
    password: str = ""
    app_key: str = ""
    cert_path: str = "./certs/betfair.pem"
    key_path: str = "./certs/betfair.key"

    model_config = {"env_prefix": "BETFAIR_"}


class PolymarketSettings(BaseSettings):
    private_key: str = ""
    api_key: str = ""
    api_secret: str = ""
    api_passphrase: str = ""
    funder_address: str = ""
    clob_url: str = "https://clob.polymarket.com"
    gamma_url: str = "https://gamma-api.polymarket.com"
    ws_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/"
    chain_id: int = 137

    model_config = {"env_prefix": "POLYMARKET_"}


class BotSettings(BaseSettings):
    demo_mode: bool = True
    min_edge_percent: float = 2.0
    max_position_usdc: float = 100.0
    max_daily_loss_usdc: float = 50.0
    poll_interval_ms: int = 500

    model_config = {"env_prefix": ""}


class ServerSettings(BaseSettings):
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "sqlite:///./data/trades.db"

    model_config = {"env_prefix": ""}


class Settings(BaseSettings):
    betfair: BetfairSettings = Field(default_factory=BetfairSettings)
    polymarket: PolymarketSettings = Field(default_factory=PolymarketSettings)
    bot: BotSettings = Field(default_factory=BotSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)


settings = Settings()
