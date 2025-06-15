import asyncio
import inspect
import logging
from functools import wraps
from typing import Any, Callable

def debug(func: Callable) -> Callable:
    if hasattr(func, "__wrapped__"):
        return func

    if isinstance(func, classmethod):
        return classmethod(debug(func.__func__))

    if isinstance(func, staticmethod):
        return staticmethod(debug(func.__func__))

    logger = logging.getLogger(func.__module__)

    if asyncio.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            logger.debug("→ %s args=%r kwargs=%r", func.__qualname__, args, kwargs)
            result = await func(*args, **kwargs)
            logger.debug("← %s result=%r", func.__qualname__, result)
            return result
        return async_wrapper

    @wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        logger.debug("→ %s args=%r kwargs=%r", func.__qualname__, args, kwargs)
        result = func(*args, **kwargs)
        logger.debug("← %s result=%r", func.__qualname__, result)
        return result
    return sync_wrapper


def debug_all(globals_dict: dict[str, Any]) -> None:
    for name, obj in list(globals_dict.items()):
        if name in {"debug", "debug_all"}:
            continue

        if inspect.isfunction(obj):
            globals_dict[name] = debug(obj)

        elif inspect.isclass(obj):
            for attr_name, attr in vars(obj).items():
                if attr_name.startswith("__"):
                    continue
                if inspect.isfunction(attr) or isinstance(attr, (classmethod, staticmethod)):
                    setattr(obj, attr_name, debug(attr))
