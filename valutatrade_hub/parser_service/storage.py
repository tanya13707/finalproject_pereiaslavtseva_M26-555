"""Хранение текущих курсов и истории."""

import math
from datetime import datetime, timezone

from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.parser_service.config import ParserConfig


class RatesStorage:
    """Чтение и сохранение курсов."""

    def __init__(self, config: ParserConfig | None = None):
        self.config = config if config is not None else ParserConfig()
        self.db = DatabaseManager()
        self.rates_path = str(self.config.RATES_FILE_PATH.resolve())
        self.history_path = str(self.config.HISTORY_FILE_PATH.resolve())

    def read_cache(self) -> dict:
        """Прочитать последние курсы."""
        data = self.db.read(
            self.rates_path,
            default={"pairs": {}, "last_refresh": None},
        )
        if not isinstance(data, dict) or not isinstance(data.get("pairs"), dict):
            raise ValueError("Неверный формат файла текущих курсов.")
        return data

    def read_history(self) -> list:
        """Прочитать историю курсов."""
        data = self.db.read(self.history_path, default=[])
        if not isinstance(data, list):
            raise ValueError("История курсов должна быть списком.")
        if any(not isinstance(record, dict) or "id" not in record for record in data):
            raise ValueError("В истории курсов есть некорректная запись.")
        return data

    @staticmethod
    def _parse_time(value: str) -> datetime:
        """Прочитать дату с часовым поясом."""
        try:
            result = datetime.fromisoformat(value)
        except (TypeError, ValueError):
            raise ValueError("Некорректная дата обновления курса.") from None

        if result.tzinfo is None:
            raise ValueError("У даты курса должен быть часовой пояс.")

        return result.astimezone(timezone.utc)

    @staticmethod
    def _validate_pair(pair: str, rate) -> None:
        """Проверить валютную пару и курс."""
        if not isinstance(pair, str):
            raise ValueError("Валютная пара должна быть строкой.")

        codes = pair.split("_")
        if len(codes) != 2:
            raise ValueError(f"Некорректная валютная пара: {pair}.")

        for code in codes:
            if (
                not 2 <= len(code) <= 5
                or not code.isascii()
                or not code.isalpha()
                or code != code.upper()
            ):
                raise ValueError(f"Некорректный код валюты: {code}.")

        if isinstance(rate, bool) or not isinstance(rate, (int, float)):
            raise ValueError(f"Курс {pair} должен быть числом.")

        if not math.isfinite(rate) or rate <= 0:
            raise ValueError(
                f"Курс {pair} должен быть положительным конечным числом."
            )


    def save_rates(self, pairs: dict) -> int:
        """Сохранить курсы и добавить записи в историю."""
        if not isinstance(pairs, dict):
            raise ValueError("Курсы должны быть словарём.")

        if not pairs:
            return 0

        records = []

        for pair, item in pairs.items():
            if not isinstance(item, dict):
                raise ValueError(f"Неверные данные для пары {pair}.")

            rate = item.get("rate")
            self._validate_pair(pair, rate)
            updated = self._parse_time(item.get("updated_at"))
            timestamp = updated.isoformat().replace("+00:00", "Z")

            source = item.get("source")
            if not isinstance(source, str) or not source.strip():
                raise ValueError(f"Не указан источник курса {pair}.")

            meta = item.get("meta", {})
            if not isinstance(meta, dict):
                raise ValueError(f"Неверные метаданные курса {pair}.")

            from_code, to_code = pair.split("_")
            records.append(
                {
                    "id": f"{pair}_{timestamp}",
                    "from_currency": from_code,
                    "to_currency": to_code,
                    "rate": float(rate),
                    "timestamp": timestamp,
                    "source": source.strip(),
                    "meta": meta.copy(),
                }
            )

        cache = self.read_cache()
        history = self.read_history()
        known_ids = {record["id"] for record in history}
        updated_count = 0

        for record in records:
            if record["id"] not in known_ids:
                history.append(record)
                known_ids.add(record["id"])

            pair = f"{record['from_currency']}_{record['to_currency']}"
            current = cache["pairs"].get(pair)

            if current is not None:
                if not isinstance(current, dict):
                    raise ValueError(f"Некорректные данные курса {pair}.")
                current_time = self._parse_time(current.get("updated_at"))
                new_time = self._parse_time(record["timestamp"])
                if new_time <= current_time:
                    continue

            cache["pairs"][pair] = {
                "rate": record["rate"],
                "updated_at": record["timestamp"],
                "source": record["source"],
            }
            updated_count += 1

        self.db.write(self.history_path, history)

        if updated_count:
            cache["last_refresh"] = (
                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            )
            self.db.write(self.rates_path, cache)

        return updated_count        