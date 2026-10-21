"""Модели пользователя, валютного кошелька и портфеля."""

import hashlib
import hmac
import math
from datetime import datetime

from valutatrade_hub.core.utils import get_usd_rate, is_rate_fresh, load_rates
from valutatrade_hub.infra.settings import SettingsLoader


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


class Wallet:
    """Кошелёк для хранения средств в одной валюте."""

    def __init__(self, currency_code: str, balance: float = 0.0):
        self.currency_code = currency_code
        self.balance = balance

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Баланс должен быть числом.")
        if not math.isfinite(value) or value < 0:
            raise ValueError("Баланс должен быть конечным неотрицательным числом.")
        self._balance = float(value)

    def deposit(self, amount: float) -> None:
        """Пополнить кошелёк на положительную сумму."""
        self._validate_amount(amount)
        self.balance += amount

    def withdraw(self, amount: float) -> None:
        """Списать средства при достаточном балансе."""
        self._validate_amount(amount)
        if amount > self.balance:
            raise ValueError(
                f"Недостаточно средств: доступно {self.balance} "
                f"{self.currency_code}, требуется {amount}."
            )
        self.balance -= amount

    def get_balance_info(self) -> str:
        """Вернуть код валюты и текущий баланс."""
        return f"{self.currency_code}: {self.balance:.4f}"

    @staticmethod
    def _validate_amount(amount: float) -> None:
        """Проверить, что сумма является положительным конечным числом."""
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise ValueError("Сумма должна быть числом.")
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError("Сумма должна быть конечным положительным числом.")


class Portfolio:
    """Валютный портфель пользователя."""

    def __init__(
        self,
        user: User,
        wallets: dict[str, Wallet] | None = None,
    ):
        self._user = user
        self._user_id = user.user_id
        self._wallets = wallets.copy() if wallets is not None else {}

    @property
    def user(self) -> User:
        return self._user

    @property
    def wallets(self) -> dict[str, Wallet]:
        return self._wallets.copy()

    def add_currency(self, currency_code: str) -> None:
        """Создать кошелёк, если такой валюты ещё нет."""
        if currency_code not in self._wallets:
            self._wallets[currency_code] = Wallet(currency_code)

    def get_wallet(self, currency_code: str) -> Wallet:
        """Получить существующий кошелёк по коду валюты."""
        if currency_code not in self._wallets:
            raise ValueError(f"Кошелёк для валюты {currency_code} не найден.")
        return self._wallets[currency_code]

    def get_wallet_values(self, base_currency: str = "USD") -> dict[str, float]:
        """Рассчитать стоимость кошельков по свежим курсам из кеша."""
        if not isinstance(base_currency, str) or not base_currency.strip():
            raise ValueError("Укажите базовую валюту.")

        base_currency = base_currency.strip().upper()
        pairs = load_rates()
        ttl = SettingsLoader().get("rates_ttl")
        codes = set(self._wallets) | {base_currency}
        usd_rates = {}

        for code in codes:
            usd_rates[code] = get_usd_rate(code, pairs)

            if code == "USD":
                continue

            updated_at = pairs[f"{code}_USD"].get("updated_at")
            if not is_rate_fresh(updated_at, ttl):
                raise ValueError(
                    f"Курс {code}→USD устарел или дата обновления некорректна. "
                    "Необходимо обновить курсы."
                )

        values = {}
        for code, wallet in self._wallets.items():
            values[code] = wallet.balance * usd_rates[code] / usd_rates[base_currency]
        return values

    def get_total_value(self, base_currency: str = "USD") -> float:
        """Рассчитать общую стоимость портфеля в базовой валюте."""
        return sum(self.get_wallet_values(base_currency).values())
