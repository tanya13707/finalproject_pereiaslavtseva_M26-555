"""Обновление курсов из внешних источников."""

import logging
from datetime import datetime, timezone

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.api_clients import (
    BaseApiClient,
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage


class RatesUpdater:
    """Получение и сохранение новых курсов."""

    def __init__(
        self,
        clients: list[BaseApiClient] | None = None,
        storage: RatesStorage | None = None,
        config: ParserConfig | None = None,
    ):
        self.config = config if config is not None else ParserConfig()
        self.storage = (
            storage if storage is not None else RatesStorage(self.config)
        )
        self.clients = (
            clients
            if clients is not None
            else [
                CoinGeckoClient(self.config),
                ExchangeRateApiClient(self.config),
            ]
        )
        self.logger = logging.getLogger("valutatrade.parser")

    def run_update(self) -> dict:
        """Обновить курсы и вернуть результат."""
        self.logger.info("Начато обновление курсов.")
        pairs = {}
        errors = []

        for client in self.clients:
            self.logger.info("Запрос курсов: %s.", client.source)

            try:
                rates = client.fetch_rates()
            except ApiRequestError as error:
                self.logger.error("%s", error)
                errors.append(str(error))
                continue

            timestamp = (
                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            )

            for pair, rate in rates.items():
                meta = client.last_meta.copy()
                code = pair.split("_")[0]

                if isinstance(client, CoinGeckoClient):
                    meta["raw_id"] = client.config.CRYPTO_ID_MAP.get(code)

                pairs[pair] = {
                    "rate": rate,
                    "updated_at": timestamp,
                    "source": client.source,
                    "meta": meta,
                }

            self.logger.info(
                "%s: получено курсов — %s.",
                client.source,
                len(rates),
            )

        if not pairs:
            self.logger.error("Не получено ни одного курса.")
            raise ApiRequestError(
                "Не удалось обновить курсы. Подробности в logs/parser.log."
            )

        try:
            updated_count = self.storage.save_rates(pairs)
            cache = self.storage.read_cache()
        except (ValueError, OSError):
            self.logger.exception("Не удалось сохранить курсы.")
            raise

        self.logger.info(
            "Обновление завершено. Обновлено: %s. Ошибок источников: %s.",
            updated_count,
            len(errors),
        )

        return {
            "updated_count": updated_count,
            "last_refresh": cache["last_refresh"],
            "errors": errors,
        }