"""Получение курсов из внешних API."""

import math
from abc import ABC, abstractmethod

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig


class BaseApiClient(ABC):
    """Общий класс для получения курсов."""

    source = ""

    def __init__(self, config: ParserConfig | None = None):
        self.config = config if config is not None else ParserConfig()
        self.last_meta = {}

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """Получить курсы валют."""
        raise NotImplementedError

    def _request_json(self, url: str, params: dict | None = None) -> dict:
        """Отправить запрос и прочитать ответ."""
        try:
            response = requests.get(
                url,
                params=params,
                timeout=self.config.REQUEST_TIMEOUT,
            )
        except requests.exceptions.Timeout:
            raise ApiRequestError(
                f"{self.source}: превышено время ожидания."
            ) from None
        except requests.exceptions.RequestException:
            raise ApiRequestError(
                f"{self.source}: не удалось подключиться к сервису."
            ) from None

        if response.status_code == 429:
            raise ApiRequestError(
                f"{self.source}: превышен лимит запросов."
            )

        if response.status_code in (401, 403):
            raise ApiRequestError(
                f"{self.source}: доступ запрещён, проверьте API-ключ."
            )

        if response.status_code != 200:
            raise ApiRequestError(
                f"{self.source}: ошибка HTTP {response.status_code}."
            )

        try:
            data = response.json()
        except ValueError:
            raise ApiRequestError(
                f"{self.source}: ответ содержит некорректный JSON."
            ) from None

        if not isinstance(data, dict):
            raise ApiRequestError(
                f"{self.source}: неверный формат ответа."
            )

        self.last_meta = {
            "request_ms": round(response.elapsed.total_seconds() * 1000),
            "status_code": response.status_code,
            "etag": response.headers.get("ETag"),
        }
        return data

    def _validate_rate(self, value, pair: str) -> float:
        """Проверить полученный курс."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ApiRequestError(
                f"{self.source}: курс {pair} должен быть числом."
            )

        if not math.isfinite(value) or value <= 0:
            raise ApiRequestError(
                f"{self.source}: курс {pair} должен быть положительным "
                "конечным числом."
            )

        return float(value)


class CoinGeckoClient(BaseApiClient):
    """Получение курсов криптовалют."""

    source = "CoinGecko"

    def fetch_rates(self) -> dict[str, float]:
        """Получить цены криптовалют в базовой валюте."""
        coin_ids = {}

        for code in self.config.CRYPTO_CURRENCIES:
            raw_id = self.config.CRYPTO_ID_MAP.get(code)
            if not raw_id:
                raise ApiRequestError(
                    f"CoinGecko: не указан ID валюты {code}."
                )
            coin_ids[code] = raw_id

        if not coin_ids:
            return {}

        base = self.config.BASE_CURRENCY
        data = self._request_json(
            self.config.COINGECKO_URL,
            params={
                "ids": ",".join(coin_ids.values()),
                "vs_currencies": base.lower(),
            },
        )

        rates = {}

        for code, raw_id in coin_ids.items():
            coin_data = data.get(raw_id)
            if not isinstance(coin_data, dict):
                raise ApiRequestError(
                    f"CoinGecko: нет данных для {code}."
                )

            pair = f"{code}_{base}"
            value = coin_data.get(base.lower())
            rates[pair] = self._validate_rate(value, pair)

        return rates


class ExchangeRateApiClient(BaseApiClient):
    """Получение курсов обычных валют."""

    source = "ExchangeRate-API"

    def fetch_rates(self) -> dict[str, float]:
        """Получить курсы валют к базовой валюте."""
        key = self.config.EXCHANGERATE_API_KEY.strip()
        if not key:
            raise ApiRequestError(
                "ExchangeRate-API: задайте переменную EXCHANGERATE_API_KEY."
            )

        base = self.config.BASE_CURRENCY
        url = (
            f"{self.config.EXCHANGERATE_API_URL.rstrip('/')}"
            f"/{key}/latest/{base}"
        )
        data = self._request_json(url)

        if data.get("result") != "success":
            error_type = data.get("error-type")
            messages = {
                "invalid-key": "неверный API-ключ",
                "inactive-account": "подтвердите регистрацию по электронной почте",
                "quota-reached": "превышен лимит запросов",
                "unsupported-code": "базовая валюта не поддерживается",
                "malformed-request": "неверный формат запроса",
            }
            reason = messages.get(error_type, "сервис вернул ошибку")
            raise ApiRequestError(f"ExchangeRate-API: {reason}.")

        if data.get("base_code") != base:
            raise ApiRequestError(
                "ExchangeRate-API: неверная базовая валюта в ответе."
            )

        conversion_rates = data.get("conversion_rates")
        if not isinstance(conversion_rates, dict):
            raise ApiRequestError(
                "ExchangeRate-API: в ответе нет словаря курсов."
            )

        rates = {}

        for code in self.config.FIAT_CURRENCIES:
            pair = f"{code}_{base}"

            if code == base:
                rates[pair] = 1.0
                continue

            value = conversion_rates.get(code)
            direct_rate = self._validate_rate(value, f"{base}_{code}")
            rates[pair] = self._validate_rate(1 / direct_rate, pair)

        return rates    