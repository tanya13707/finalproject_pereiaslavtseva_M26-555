"""Вспомогательные функции для работы с курсами валют."""

from datetime import datetime, timezone

from valutatrade_hub.infra.database import DatabaseManager


def load_rates() -> dict:
    """Прочитать валютные пары через общее JSON-хранилище."""
    data = DatabaseManager().read(
        "rates.json",
        default={"pairs": {}, "last_refresh": None},
    )
    return data["pairs"]


def get_usd_rate(currency_code: str, pairs: dict) -> float:
    """Получить стоимость единицы валюты в USD."""
    if currency_code == "USD":
        return 1.0

    pair = f"{currency_code}_USD"
    if pair not in pairs:
        raise ValueError(f"Нет сохранённого курса {pair}.")
    rate = pairs[pair]["rate"]

    if isinstance(rate, bool) or not isinstance(rate, (int, float)):
        raise ValueError(f"Некорректный курс {pair}.")
    if not 0 < rate < float("inf"):
        raise ValueError(f"Курс {pair} должен быть положительным конечным числом.")

    return float(rate)


def is_rate_fresh(updated_at: str, ttl_seconds: int) -> bool:
    """Проверить, что возраст курса меньше срока актуальности."""
    try:
        updated = datetime.fromisoformat(updated_at)
    except (TypeError, ValueError):
        return False

    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)

    age = (datetime.now(timezone.utc) - updated).total_seconds()
    return 0 <= age < ttl_seconds