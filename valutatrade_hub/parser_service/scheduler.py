"""Обновление курсов через заданный интервал."""

import argparse
import logging
import time

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.logging_config import setup_logging
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.updater import RatesUpdater


def run_scheduler(interval: int | None = None) -> None:
    """Обновлять курсы до остановки пользователем."""
    config = ParserConfig()
    interval = config.UPDATE_INTERVAL if interval is None else interval

    if isinstance(interval, bool) or not isinstance(interval, int) or interval <= 0:
        raise ValueError("Интервал должен быть целым числом больше 0.")

    setup_logging()
    logger = logging.getLogger("valutatrade.parser")
    updater = RatesUpdater(config=config)

    print(f"Обновление каждые {interval} секунд. Остановка: Ctrl + C.")
    logger.info("Планировщик запущен. Интервал: %s секунд.", interval)

    try:
        while True:
            try:
                result = updater.run_update()
            except (ApiRequestError, ValueError, OSError) as error:
                logger.error("Ошибка обновления: %s", error)
                print(f"Не удалось обновить курсы: {error}")
            else:
                print(
                    f"Обновлено курсов: {result['updated_count']}. "
                    f"Время: {result['last_refresh']}"
                )
                if result["errors"]:
                    print("Есть ошибки источников. Подробности в logs/parser.log.")

            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Планировщик остановлен пользователем.")
        print("\nПланировщик остановлен.")


def main() -> None:
    """Запустить планировщик из терминала."""
    parser = argparse.ArgumentParser(description="Обновление курсов по таймеру")
    parser.add_argument(
        "--interval",
        type=int,
        help="Интервал обновления в секундах",
    )
    args = parser.parse_args()

    if args.interval is not None and args.interval <= 0:
        parser.error("Интервал должен быть больше 0.")

    run_scheduler(args.interval)


if __name__ == "__main__":
    main()