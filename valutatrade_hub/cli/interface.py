"""Консольный интерфейс приложения."""

import argparse
import shlex
import sys

from valutatrade_hub.core.usecases import get_portfolio_summary, login, register


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

    return parser


def main() -> None:
    """Обрабатывать команды и хранить текущую сессию."""
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

        except (ValueError, OSError) as error:
            print(f"Ошибка: {error}")
        except (EOFError, KeyboardInterrupt):
            print("\nРабота завершена.")
            break

        if single_command:
            break


if __name__ == "__main__":
    main()