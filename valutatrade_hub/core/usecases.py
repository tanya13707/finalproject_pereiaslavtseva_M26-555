"""Операции с пользователями и валютными портфелями."""

import math
import secrets
from datetime import datetime, timezone

from valutatrade_hub.core.currencies import CryptoCurrency, get_currency
from valutatrade_hub.core.models import Portfolio, User, Wallet
from valutatrade_hub.core.utils import get_usd_rate, is_rate_fresh, load_rates
from valutatrade_hub.decorators import log_action, set_action_details
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater


def register(username: str, password: str) -> User:
    """Зарегистрировать пользователя и создать пустой портфель."""
    db = DatabaseManager()
    users = db.read("users.json", default=[])
    portfolios = db.read("portfolios.json", default=[])

    if not isinstance(username, str) or not username.strip():
        raise ValueError("Имя пользователя не должно быть пустым.")

    username = username.strip()

    for existing_user in users:
        if existing_user["username"] == username:
            raise ValueError("Это имя пользователя уже занято.")

    user_id = 1
    for existing_user in users:
        if existing_user["user_id"] >= user_id:
            user_id = existing_user["user_id"] + 1

    user = User(
        user_id=user_id,
        username=username,
        hashed_password="",
        salt=secrets.token_hex(16),
        registration_date=datetime.now(timezone.utc),
    )
    user.change_password(password)

    user_data = {
        "user_id": user.user_id,
        "username": user.username,
        "hashed_password": user.hashed_password,
        "salt": user.salt,
        "registration_date": user.registration_date.isoformat(),
    }

    users.append(user_data)
    portfolios.append({"user_id": user.user_id, "wallets": {}})

    db.write("portfolios.json", portfolios)
    try:
        db.write("users.json", users)
    except OSError:
        portfolios.pop()
        db.write("portfolios.json", portfolios)
        raise

    return user


def login(username: str, password: str) -> User:
    """Проверить имя и пароль пользователя."""
    if not isinstance(username, str) or not username.strip():
        raise ValueError("Имя пользователя не должно быть пустым.")

    username = username.strip()
    db = DatabaseManager()
    users = db.read("users.json", default=[])

    for record in users:
        if record["username"] == username:
            user = User(
                user_id=record["user_id"],
                username=record["username"],
                hashed_password=record["hashed_password"],
                salt=record["salt"],
                registration_date=datetime.fromisoformat(record["registration_date"]),
            )

            if not user.verify_password(password):
                raise ValueError("Неверный пароль.")

            return user

    raise ValueError("Пользователь не найден.")


def load_portfolio(user: User) -> Portfolio:
    """Загрузить кошельки пользователя из JSON."""
    db = DatabaseManager()
    portfolios = db.read("portfolios.json", default=[])

    for record in portfolios:
        if record["user_id"] == user.user_id:
            wallets = {}

            for code, wallet_data in record["wallets"].items():
                wallets[code] = Wallet(
                    currency_code=code,
                    balance=wallet_data["balance"],
                )

            return Portfolio(user, wallets)

    raise ValueError("Портфель пользователя не найден.")


def save_portfolio(portfolio: Portfolio) -> None:
    """Сохранить текущие балансы кошельков пользователя."""
    db = DatabaseManager()
    portfolios = db.read("portfolios.json", default=[])

    for record in portfolios:
        if record["user_id"] == portfolio.user.user_id:
            wallets = {}

            for code, wallet in portfolio.wallets.items():
                wallets[code] = {"balance": wallet.balance}

            record["wallets"] = wallets
            db.write("portfolios.json", portfolios)
            return

    raise ValueError("Портфель пользователя не найден.")


@log_action("BUY", verbose=True)
def buy(
    user: User,
    currency_code: str,
    amount: float,
) -> Portfolio:
    """Купить валюту за USD по курсу из локального кеша."""

    currency_code = get_currency(currency_code).code
    if currency_code == "USD":
        raise ValueError("Для покупки выберите валюту, отличную от USD.")

    rate = get_rate(currency_code, "USD")["rate"]
    set_action_details(currency_code=currency_code, rate=rate)
    for name, value in (("Количество", amount), ("Курс", rate)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} должно быть числом.")
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} должно быть положительным конечным числом.")

    cost = amount * rate
    if not math.isfinite(cost) or cost <= 0:
        raise ValueError("Некорректная стоимость покупки.")

    portfolio = load_portfolio(user)
    set_action_details(
        before={
            code: wallet.balance
            for code, wallet in portfolio.wallets.items()
        }
    )

    if "USD" not in portfolio.wallets:
        raise ValueError("Для покупки нужен USD-кошелёк со средствами.")

    usd_wallet = portfolio.get_wallet("USD")
    usd_wallet.withdraw(cost)

    portfolio.add_currency(currency_code)
    portfolio.get_wallet(currency_code).deposit(amount)

    save_portfolio(portfolio)
    set_action_details(
        after={
            code: wallet.balance
            for code, wallet in portfolio.wallets.items()
        }
    )
    return portfolio


@log_action("SELL", verbose=True)
def sell(
    user: User,
    currency_code: str,
    amount: float,
) -> Portfolio:
    """Продать валюту за USD по курсу из локального кеша."""
   
    currency_code = get_currency(currency_code).code
    if currency_code == "USD":
        raise ValueError("Для продажи выберите валюту, отличную от USD.")

    rate = get_rate(currency_code, "USD")["rate"]
    set_action_details(currency_code=currency_code, rate=rate)

    for name, value in (("Количество", amount), ("Курс", rate)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} должно быть числом.")
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} должно быть положительным конечным числом.")

    proceeds = amount * rate
    if not math.isfinite(proceeds) or proceeds <= 0:
        raise ValueError("Некорректная сумма продажи.")

    portfolio = load_portfolio(user)
    set_action_details(
        before={
            code: wallet.balance
            for code, wallet in portfolio.wallets.items()
        }
    )
    currency_wallet = portfolio.get_wallet(currency_code)
    currency_wallet.withdraw(amount)

    portfolio.add_currency("USD")
    portfolio.get_wallet("USD").deposit(proceeds)

    save_portfolio(portfolio)
    set_action_details(
        after={
            code: wallet.balance
            for code, wallet in portfolio.wallets.items()
        }
    )
    return portfolio


def get_portfolio_summary(user: User, base_currency: str = "USD") -> dict:
    """Получить балансы кошельков и стоимость портфеля."""
    base_currency = base_currency.strip().upper()
    portfolio = load_portfolio(user)
    values = portfolio.get_wallet_values(base_currency)

    wallets = []
    for code, wallet in portfolio.wallets.items():
        wallets.append(
            {
                "currency_code": code,
                "balance": wallet.balance,
                "value": values[code],
            }
        )

    return {
        "username": user.username,
        "base_currency": base_currency,
        "wallets": wallets,
        "total": sum(values.values()),
    }


def get_rate(from_code: str, to_code: str) -> dict:
    """Получить курс из локального кеша с проверкой свежести."""
    from_code = get_currency(from_code).code
    to_code = get_currency(to_code).code
    codes = [from_code, to_code]
    pairs = load_rates()
    ttl = SettingsLoader().get("rates_ttl")
    timestamps = []

    for code in set(codes):
        if code == "USD":
            continue

        get_usd_rate(code, pairs)
        updated_at = pairs[f"{code}_USD"].get("updated_at")

        if not is_rate_fresh(updated_at, ttl):
            raise ValueError(
                f"Курс {code}→USD устарел или дата обновления некорректна. "
                "Необходимо обновить курсы."
            )

        updated = datetime.fromisoformat(updated_at)
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        timestamps.append(updated)

    rate = get_usd_rate(from_code, pairs) / get_usd_rate(to_code, pairs)
    updated = min(timestamps) if timestamps else datetime.now(timezone.utc)

    return {
        "from_currency": from_code,
        "to_currency": to_code,
        "rate": rate,
        "updated_at": updated.isoformat(),
    }


def update_rates(source: str | None = None) -> dict:
    """Обновить курсы из выбранного источника."""
    config = ParserConfig()

    if source is None:
        clients = [
            CoinGeckoClient(config),
            ExchangeRateApiClient(config),
        ]
    elif source == "coingecko":
        clients = [CoinGeckoClient(config)]
    elif source == "exchangerate":
        clients = [ExchangeRateApiClient(config)]
    else:
        raise ValueError("Источник должен быть coingecko или exchangerate.")

    updater = RatesUpdater(clients=clients, config=config)
    return updater.run_update()


def get_rates_summary(
    currency: str | None = None,
    top: int | None = None,
    base: str = "USD",
) -> dict:
    """Подготовить курсы из кеша для вывода."""
    base = get_currency(base).code

    if currency is not None:
        currency = get_currency(currency).code

    if top is not None:
        if isinstance(top, bool) or not isinstance(top, int) or top <= 0:
            raise ValueError("Количество валют должно быть целым числом больше 0.")

    cache = RatesStorage().read_cache()
    pairs = cache["pairs"]

    if not pairs:
        raise ValueError(
            "Локальный кеш курсов пуст. "
            "Выполните 'update-rates', чтобы загрузить данные."
        )

    base_rate = get_usd_rate(base, pairs)
    ttl = SettingsLoader().get("rates_ttl")
    codes = {
        pair.removesuffix("_USD")
        for pair in pairs
        if pair.endswith("_USD")
    }

    if currency is not None:
        if currency != "USD" and currency not in codes:
            raise ValueError(f"Курс для '{currency}' не найден в кеше.")
        codes = {currency}

    rows = []

    for code in sorted(codes):
        coin = get_currency(code)

        if top is not None and not isinstance(coin, CryptoCurrency):
            continue

        rate = get_usd_rate(code, pairs) / base_rate
        dates = []

        for checked_code in {code, base}:
            if checked_code != "USD":
                dates.append(pairs[f"{checked_code}_USD"].get("updated_at"))

        fresh = all(is_rate_fresh(date, ttl) for date in dates)
        updated = (
            min(RatesStorage._parse_time(date) for date in dates).isoformat()
            if dates
            else datetime.now(timezone.utc).isoformat()
        )

        rows.append(
            {
                "pair": f"{code}_{base}",
                "rate": rate,
                "updated_at": updated,
                "fresh": fresh,
            }
        )

    if top is not None:
        rows.sort(key=lambda row: row["rate"], reverse=True)
        rows = rows[:top]

    return {
        "base": base,
        "last_refresh": cache["last_refresh"],
        "rates": rows,
    }