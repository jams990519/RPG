"""Wrapper fino sobre loguru para obtener loggers con contexto."""
from __future__ import annotations

from typing import Any

from loguru import logger


def get_logger(name: str, **context: Any):
    """Devuelve un logger con `name` y contexto extra ya enlazados."""
    return logger.bind(module=name, **context)


__all__ = ["get_logger", "logger"]
