"""Настройки сервиса курсов валют."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from valutatrade_hub.infra.settings import SettingsLoader


@dataclass
class ParserConfig:
    """Адреса API, валюты и параметры запросов."""

    EXCHANGERATE_API_KEY: str = field(
        default_factory=lambda: os.getenv("EXCHANGERATE_API_KEY", ""),
        repr=False,
    )

    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    BASE_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple[str, ...] = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple[str, ...] = ("BTC", "ETH", "SOL")

    CRYPTO_ID_MAP: dict[str, str] = field(
        default_factory=lambda: {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
        }
    )

    REQUEST_TIMEOUT: int = 10
    UPDATE_INTERVAL: int = 300

    RATES_FILE_PATH: Path = field(
        default_factory=lambda: (
            Path(SettingsLoader().get("data_dir", "data")) / "rates.json"
        )
    )
    HISTORY_FILE_PATH: Path = field(
        default_factory=lambda: (
            Path(SettingsLoader().get("data_dir", "data"))
            / "exchange_rates.json"
        )
    )