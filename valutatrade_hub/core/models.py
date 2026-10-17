"""Модели пользователя, валютного кошелька и портфеля."""

import hashlib
import hmac
from datetime import datetime


class User:
    """Пользователь с паролем, сохранённым в виде хеша с солью."""

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ):
        self._user_id = user_id
        self.username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не должно быть пустым.")
        self._username = value.strip()

    @property
    def hashed_password(self) -> str:
        return self._hashed_password

    @property
    def salt(self) -> str:
        return self._salt

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    def get_user_info(self) -> dict:
        """Вернуть информацию о пользователе без пароля и соли."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "registration_date": self.registration_date.isoformat(),
        }

    def change_password(self, new_password: str) -> None:
        """Проверить новый пароль и сохранить его хеш."""
        if not isinstance(new_password, str) or len(new_password) < 4:
            raise ValueError("Пароль должен содержать не менее 4 символов.")
        self._hashed_password = self._hash_password(new_password)

    def verify_password(self, password: str) -> bool:
        """Проверить пароль, сравнив хеши."""
        if not isinstance(password, str):
            return False
        return hmac.compare_digest(
            self._hashed_password,
            self._hash_password(password),
        )

    def _hash_password(self, password: str) -> str:
        """Вычислить SHA-256 от пароля с солью."""
        value = (password + self._salt).encode("utf-8")
        return hashlib.sha256(value).hexdigest()