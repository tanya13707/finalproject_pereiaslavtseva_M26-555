"""Запись операций и ошибок в лог."""

import logging
from contextvars import ContextVar
from functools import wraps
from inspect import signature

_action_details = ContextVar("action_details", default=None)


def set_action_details(**details) -> None:
    """Добавить курс и другие сведения о текущей операции."""
    context = _action_details.get()
    if context is not None:
        context.update(details)


def log_action(action: str, verbose: bool = False):
    """Записать результат операции и передать ошибку дальше."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            arguments = signature(func).bind(*args, **kwargs).arguments
            user = arguments.get("user")
            details = {
                "username": getattr(user, "username", None),
                "currency_code": arguments.get("currency_code"),
                "amount": arguments.get("amount"),
                "base": "USD",
            }
            token = _action_details.set(details)
            logger = logging.getLogger("valutatrade.actions")

            try:
                result = func(*args, **kwargs)
            except Exception as error:
                write_log(logger, action, details, verbose, error)
                raise
            else:
                write_log(logger, action, details, verbose)
                return result
            finally:
                _action_details.reset(token)

        return wrapper

    return decorator


def write_log(logger, action, details, verbose, error=None) -> None:
    """Составить запись об операции."""
    fields = {
        "action": action,
        "username": details.get("username"),
        "currency_code": details.get("currency_code"),
        "amount": details.get("amount"),
        "rate": details.get("rate"),
        "base": details.get("base"),
        "result": "ERROR" if error is not None else "OK",
    }

    if verbose:
        fields["before"] = details.get("before")
        fields["after"] = details.get("after")

    if error is not None:
        fields["error_type"] = type(error).__name__
        fields["error_message"] = str(error)

    message = " ".join(f"{key}={value!r}" for key, value in fields.items())
    logger.info(message)