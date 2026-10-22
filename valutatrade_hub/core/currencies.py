"""Классы валют и поиск валюты по коду."""

import math
from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError


class Currency(ABC):
    """Базовый класс валюты."""

    def __init__(self, name: str, code: str):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Название валюты не должно быть пустым.")

        if not isinstance(code, str):
            raise ValueError("Код валюты должен быть строкой.")

        if (
            not 2 <= len(code) <= 5
            or not code.isascii()
            or not code.isalpha()
            or code != code.upper()
        ):
            raise ValueError(
                "Код валюты — от 2 до 5 заглавных латинских букв."
            )

        self.name = name.strip()
        self.code = code

    @abstractmethod
    def get_display_info(self) -> str:
        """Вернуть информацию о валюте."""
        raise NotImplementedError


class FiatCurrency(Currency):
    """Обычная валюта: доллар, евро и другие."""

    def __init__(self, name: str, code: str, issuing_country: str):
        super().__init__(name, code)

        if not isinstance(issuing_country, str) or not issuing_country.strip():
            raise ValueError("Укажите страну или зону выпуска валюты.")

        self.issuing_country = issuing_country.strip()

    def get_display_info(self) -> str:
        """Вернуть информацию о валюте."""
        return (
            f"[FIAT] {self.code} — {self.name} "
            f"(Issuing: {self.issuing_country})"
        )    


class CryptoCurrency(Currency):
    """Криптовалюта."""

    def __init__(
        self,
        name: str,
        code: str,
        algorithm: str,
        market_cap: float,
    ):
        super().__init__(name, code)

        if not isinstance(algorithm, str) or not algorithm.strip():
            raise ValueError("Укажите алгоритм криптовалюты.")

        if isinstance(market_cap, bool) or not isinstance(market_cap, (int, float)):
            raise ValueError("Капитализация должна быть числом.")

        if not math.isfinite(market_cap) or market_cap < 0:
            raise ValueError(
                "Капитализация должна быть конечным неотрицательным числом."
            )

        self.algorithm = algorithm.strip()
        self.market_cap = float(market_cap)

    def get_display_info(self) -> str:
        """Вернуть информацию о криптовалюте."""
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self.algorithm}, MCAP: {self.market_cap:.2e})"
        )    


CURRENCIES = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "GBP": FiatCurrency("British Pound", "GBP", "United Kingdom"),
    "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Proof of Stake", 4.0e11),
    "SOL": CryptoCurrency("Solana", "SOL", "Proof of History", 7.0e10),
}


def get_currency(code: str) -> Currency:
    """Найти валюту по коду."""
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Укажите код валюты.")

    code = code.strip().upper()

    if code not in CURRENCIES:
        raise CurrencyNotFoundError(code)

    return CURRENCIES[code]    