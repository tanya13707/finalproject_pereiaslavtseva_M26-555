"""Единый менеджер чтения и записи JSON-файлов."""

import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path

from valutatrade_hub.infra.settings import SettingsLoader


class DatabaseManager:
    """Работать с JSON-хранилищами через один общий экземпляр."""

    _instance = None

    def __new__(cls):
        # Singleton: единая точка доступа к файлам данных.
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._settings = SettingsLoader()
            cls._instance = instance
        return cls._instance

    def _get_path(self, filename: str) -> Path:
        """Получить путь к файлу в папке данных."""
        return Path(self._settings.get("data_dir")) / filename

    def read(self, filename: str, default=None):
        """Прочитать JSON, вернуть default при отсутствии файла."""
        path = self._get_path(filename)
        try:
            with path.open(encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError:
            return deepcopy(default)
        except json.JSONDecodeError as error:
            raise ValueError(f"В файле {filename} повреждён JSON.") from error

    def write(self, filename: str, data) -> None:
        """Записать JSON через временный файл и замену исходного."""
        path = self._get_path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                suffix=".tmp",
                delete=False,
            ) as file:
                temporary_path = Path(file.name)
                json.dump(
                    data,
                    file,
                    ensure_ascii=False,
                    indent=2,
                    allow_nan=False,
                )
                file.write("\n")

            os.replace(temporary_path, path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
