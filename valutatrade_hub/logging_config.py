"""Настройка записи логов в файлы."""

import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from valutatrade_hub.infra.settings import SettingsLoader


def setup_logging() -> None:
    """Настроить файлы логов и их ротацию."""
    settings = SettingsLoader()
    logs_dir = Path(settings.get("logs_dir", "logs"))
    logs_dir.mkdir(parents=True, exist_ok=True)

    level = settings.get("log_level", "INFO").upper()
    log_format = settings.get(
        "log_format",
        "%(levelname)s %(asctime)sZ %(message)s",
    )
    max_bytes = settings.get("log_max_bytes", 1_000_000)
    backup_count = settings.get("log_backup_count", 3)

    formatter = logging.Formatter(
        log_format,
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    formatter.converter = time.gmtime

    for name, filename in (
        ("valutatrade.actions", "actions.log"),
        ("valutatrade.parser", "parser.log"),
    ):
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = False

        if logger.handlers:
            continue

        handler = RotatingFileHandler(
            logs_dir / filename,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)