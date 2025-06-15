import asyncio
import inspect
from functools import wraps
from typing import Any, Callable

import logging


def debug(func: Callable) -> Callable:
    """Decorator to log function entry and exit at DEBUG level."""
    logger = logging.getLogger(func.__module__)

    if asyncio.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            logger.debug("Entering %s args=%r kwargs=%r", func.__qualname__, args, kwargs)
            result = await func(*args, **kwargs)
            logger.debug("Exiting %s result=%r", func.__qualname__, result)
            return result
        return async_wrapper

    @wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        logger.debug("Entering %s args=%r kwargs=%r", func.__qualname__, args, kwargs)
        result = func(*args, **kwargs)
        logger.debug("Exiting %s result=%r", func.__qualname__, result)
        return result
    return sync_wrapper


def debug_all(globals_dict: dict[str, Any]) -> None:
    """Wrap all functions and class methods in ``globals_dict`` with :func:`debug`."""
    for name, obj in list(globals_dict.items()):
        if name in {"debug", "debug_all"}:
            continue
        if inspect.isfunction(obj):
            globals_dict[name] = debug(obj)
        elif inspect.isclass(obj):
            for attr_name, attr in list(vars(obj).items()):
                if inspect.isfunction(attr) or inspect.ismethoddescriptor(attr):
                    if attr_name.startswith("__") or not hasattr(attr, "__module__"):
                        continue
                    setattr(obj, attr_name, debug(attr))
