"""Операции с пользователями и валютными портфелями."""

import math
import secrets
from datetime import datetime, timezone

from valutatrade_hub.core.models import Portfolio, User, Wallet
from valutatrade_hub.infra.database import DatabaseManager


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


def buy(
    user: User,
    currency_code: str,
    amount: float,
    rate: float,
) -> Portfolio:
    """Купить валюту за USD по переданному курсу."""
    if not isinstance(currency_code, str) or not currency_code.strip():
        raise ValueError("Укажите код валюты.")

    currency_code = currency_code.strip().upper()
    if currency_code == "USD":
        raise ValueError("Для покупки выберите валюту, отличную от USD.")

    for name, value in (("Количество", amount), ("Курс", rate)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} должно быть числом.")
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} должно быть положительным конечным числом.")

    cost = amount * rate
    if not math.isfinite(cost) or cost <= 0:
        raise ValueError("Некорректная стоимость покупки.")

    portfolio = load_portfolio(user)

    if "USD" not in portfolio.wallets:
        raise ValueError("Для покупки нужен USD-кошелёк со средствами.")

    usd_wallet = portfolio.get_wallet("USD")
    usd_wallet.withdraw(cost)

    portfolio.add_currency(currency_code)
    portfolio.get_wallet(currency_code).deposit(amount)

    save_portfolio(portfolio)
    return portfolio
