"""Консольный интерфейс приложения."""

import argparse
import shlex
import sys

from prettytable import PrettyTable

from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.core.usecases import (
    buy,
    get_portfolio_summary,
    get_rate,
    get_rates_summary,
    login,
    register,
    sell,
    update_rates,
)
from valutatrade_hub.logging_config import setup_logging


def create_parser() -> argparse.ArgumentParser:
    """Создать парсер команд приложения."""
    parser = argparse.ArgumentParser(prog="valutatrade")
    commands = parser.add_subparsers(dest="command", required=True)

    register_parser = commands.add_parser(
        "register", help="Зарегистрировать пользователя"
    )
    register_parser.add_argument("--username", required=True)
    register_parser.add_argument("--password", required=True)

    login_parser = commands.add_parser("login", help="Войти в аккаунт")
    login_parser.add_argument("--username", required=True)
    login_parser.add_argument("--password", required=True)

    portfolio_parser = commands.add_parser(
        "show-portfolio", help="Показать портфель пользователя"
    )
    portfolio_parser.add_argument("--base", default="USD")

    buy_parser = commands.add_parser("buy", help="Купить валюту")
    buy_parser.add_argument("--currency", required=True)
    buy_parser.add_argument("--amount", type=float, required=True)

    sell_parser = commands.add_parser("sell", help="Продать валюту")
    sell_parser.add_argument("--currency", required=True)
    sell_parser.add_argument("--amount", type=float, required=True)

    rate_parser = commands.add_parser(
        "get-rate",
        help="Получить курс одной валюты к другой",
    )
    rate_parser.add_argument("--from", dest="from_code", required=True)
    rate_parser.add_argument("--to", dest="to_code", required=True)
    update_parser = commands.add_parser(
        "update-rates",
        help="Обновить курсы валют",
    )
    update_parser.add_argument(
        "--source",
        choices=("coingecko", "exchangerate"),
        help="Обновить только выбранный источник",
    )

    show_rates_parser = commands.add_parser(
        "show-rates",
        help="Показать курсы из кеша",
    )
    show_rates_parser.add_argument(
        "--currency",
        help="Показать курс выбранной валюты",
    )
    show_rates_parser.add_argument(
        "--top",
        type=int,
        help="Показать самые дорогие криптовалюты",
    )
    show_rates_parser.add_argument(
        "--base",
        default="USD",
        help="Базовая валюта, по умолчанию USD",
    )
    return parser


def main() -> None:
    """Обрабатывать команды и хранить текущую сессию."""
    setup_logging()
    parser = create_parser()
    current_user = None
    single_command = bool(sys.argv[1:])

    if not single_command:
        print("ValutaTrade Hub. Справка: help. Выход: exit.")

    while True:
        try:
            if single_command:
                arguments = sys.argv[1:]
            else:
                command = input("valutatrade> ").strip()

                if not command:
                    continue
                if command == "exit":
                    break
                if command == "help":
                    parser.print_help()
                    continue

                arguments = shlex.split(command)

            try:
                args = parser.parse_args(arguments)
            except SystemExit:
                if single_command:
                    raise
                continue

            if args.command == "register":
                user = register(args.username, args.password)
                print(
                    f"Пользователь '{user.username}' зарегистрирован "
                    f"(id={user.user_id}). Выполните login."
                )
            elif args.command == "login":
                current_user = login(args.username, args.password)
                print(f"Вы вошли как '{current_user.username}'.")

            elif args.command == "show-portfolio":
                if current_user is None:
                    print("Сначала выполните login")
                else:
                    summary = get_portfolio_summary(current_user, args.base)
                    base = summary["base_currency"]

                    print(
                        f"Портфель пользователя '{summary['username']}' "
                        f"(база: {base}):"
                    )

                    if not summary["wallets"]:
                        print("Ваш портфель пока пуст.")
                    else:
                        for wallet in summary["wallets"]:
                            print(
                                f"- {wallet['currency_code']}: "
                                f"{wallet['balance']:.4f} → "
                                f"{wallet['value']:,.2f} {base}"
                            )

                        print(f"ИТОГО: {summary['total']:,.2f} {base}")
            elif args.command == "buy":
                if current_user is None:
                    print("Сначала выполните login")
                else:
                    result = buy(
                        current_user, args.currency, args.amount
                    )
                    code = result["currency_code"]
                    wallet = result["portfolio"].get_wallet(code)

                    print(
                        f"Покупка выполнена: {result['amount']:.4f} {code}"
                    )
                    print(f"Курс: {result['rate']:.8f} USD/{code}")
                    print(f"Стоимость покупки: {result['total']:,.2f} USD")
                    print(f"Баланс {code}: {wallet.balance:.4f}")

            elif args.command == "sell":
                if current_user is None:
                    print("Сначала выполните login")
                else:
                    result = sell(
                        current_user, args.currency, args.amount
                    )
                    code = result["currency_code"]
                    wallet = result["portfolio"].get_wallet(code)

                    print(
                        f"Продажа выполнена: {result['amount']:.4f} {code}"
                    )
                    print(f"Курс: {result['rate']:.8f} USD/{code}")
                    print(f"Выручка от продажи: {result['total']:,.2f} USD")
                    print(f"Баланс {code}: {wallet.balance:.4f}")

            elif args.command == "get-rate":
                result = get_rate(args.from_code, args.to_code)
                from_code = result["from_currency"]
                to_code = result["to_currency"]
                rate = result["rate"]

                print(
                    f"Курс {from_code}→{to_code}: {rate:.8f} "
                    f"(обновлено: {result['updated_at']})"
                )
                print(f"Обратный курс {to_code}→{from_code}: {1 / rate:.8f}")
            elif args.command == "update-rates":
                print("Обновление курсов...")
                result = update_rates(args.source)
                print(f"Обновлено курсов: {result['updated_count']}.")
                print(f"Последнее обновление: {result['last_refresh']}")

                if result["errors"]:
                    print(
                        "Обновление выполнено частично. "
                        "Подробности в logs/parser.log."
                    )
                else:
                    print("Обновление завершено успешно.")
            elif args.command == "show-rates":
                summary = get_rates_summary(
                    currency=args.currency,
                    top=args.top,
                    base=args.base,
                )
                print(
                    "Курсы из кеша. "
                    f"Последнее обновление: {summary['last_refresh']}"
                )

                table = PrettyTable()
                table.field_names = [
                    "Пара",
                    "Курс",
                    "Обновлено",
                    "Статус",
                ]

                for row in summary["rates"]:
                    table.add_row(
                        [
                            row["pair"],
                            f"{row['rate']:.8f}",
                            row["updated_at"],
                            "Свежий" if row["fresh"] else "Устарел",
                        ]
                    )

                if summary["rates"]:
                    print(table)
                else:
                    print("Нет курсов для выбранных фильтров.")

                if any(not row["fresh"] for row in summary["rates"]):
                    print("Есть устаревшие курсы. Выполните update-rates.")            

        except ApiRequestError as error:
            print(error)
            print("Проверьте сеть и API-ключ. Повторите попытку позже.")    
        except CurrencyNotFoundError as error:
            print(error)
            print("Поддерживаемые валюты: USD, EUR, GBP, RUB, BTC, ETH, SOL.")
        except InsufficientFundsError as error:
            print(error)
        except (ValueError, OSError) as error:
            print(f"Ошибка: {error}")
        except (EOFError, KeyboardInterrupt):
            print("\nРабота завершена.")
            break

        if single_command:
            break


if __name__ == "__main__":
    main()