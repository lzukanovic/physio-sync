"""Collector configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API connection
    collector_api_ws_url: str = "ws://localhost:8000/ws/collector"

    # BITalino
    bitalino_address: str = ""
    bitalino_frequency: int = 100
    bitalino_channels: int = 0x01

    # Tobii Pro Glasses 3
    tobii_address: str = ""
    tobii_frequency: int = 100

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
