"""Настройки приложения с единственным общим экземпляром."""

import tomllib
from pathlib import Path


class SettingsLoader:
    """Загрузчик настроек приложения."""

    _instance = None

    def __new__(cls):
        # Используем __new__: это простой способ возвращать один общий экземпляр.
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._load()
            cls._instance = instance
        return cls._instance

    def _load(self) -> None:
        """Загрузить значения по умолчанию и настройки из pyproject.toml."""
        self._settings = {
            "data_dir": "data",
            "rates_ttl": 300,
            "default_base_currency": "USD",
            "logs_dir": "logs",
            "log_level": "INFO",
            "log_format": "%(levelname)s %(asctime)sZ %(message)s",
            "log_max_bytes": 1_000_000,
            "log_backup_count": 3,
        }

        config_path = Path("pyproject.toml")
        if config_path.exists():
            with config_path.open("rb") as file:
                config = tomllib.load(file)
            overrides = config.get("tool", {}).get("valutatrade", {})
            self._settings.update(overrides)

    def get(self, key: str, default=None):
        """Получить настройку по имени."""
        return self._settings.get(key, default)

    def reload(self) -> None:
        """Повторно загрузить настройки."""
        self._load()