"""Операции с пользователями и валютными портфелями."""

import secrets
from datetime import datetime, timezone

from valutatrade_hub.core.models import User
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
