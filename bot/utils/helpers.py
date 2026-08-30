"""Funciones auxiliares puras (sin dependencias de aiogram ni de la BD)."""
from __future__ import annotations

import html
import random
from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable, Sequence, TypeVar

T = TypeVar("T")

#: XP necesaria para pasar del nivel 1 al 2. Cada nivel escala de forma cuadrática.
XP_BASE = 100


def level_from_xp(xp: int) -> int:
    """Nivel correspondiente a una cantidad de XP (empieza en 1)."""
    if xp < 0:
        return 1
    return int((xp / XP_BASE) ** 0.5) + 1


def xp_for_level(level: int) -> int:
    """XP total acumulada necesaria para alcanzar `level`."""
    if level <= 1:
        return 0
    return (level - 1) ** 2 * XP_BASE


def xp_progress(xp: int) -> tuple[int, int, int]:
    """Devuelve `(nivel, xp_dentro_del_nivel, xp_necesaria_para_subir)`."""
    level = level_from_xp(xp)
    floor_xp = xp_for_level(level)
    next_xp = xp_for_level(level + 1)
    return level, xp - floor_xp, next_xp - floor_xp


def progress_bar(current: int, total: int, width: int = 10) -> str:
    """Barra de progreso en bloques unicode."""
    if total <= 0:
        return "▰" * width
    ratio = max(0.0, min(1.0, current / total))
    filled = int(round(ratio * width))
    return "▰" * filled + "▱" * (width - filled)


def format_coins(amount: int) -> str:
    """Formatea una cantidad de monedas con separador de miles."""
    return f"{amount:,}".replace(",", ".")


def format_timedelta(delta: timedelta) -> str:
    """Duración legible en español: `2h 5m`, `45s`, ..."""
    seconds = max(0, int(delta.total_seconds()))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs and not hours:
        parts.append(f"{secs}s")
    return " ".join(parts) or "0s"


def escape(text: str | None) -> str:
    """Escapa texto para el parse_mode HTML de Telegram."""
    return html.escape(text or "", quote=False)


def medal(position: int) -> str:
    """Emoji de medalla según la posición del ranking (1-indexado)."""
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(position, f"{position}.")


def clamp(value: int, minimum: int, maximum: int) -> int:
    """Restringe `value` al rango `[minimum, maximum]`."""
    return max(minimum, min(maximum, value))


def chunked(items: Sequence[T], size: int) -> list[list[T]]:
    """Parte una secuencia en trozos de como mucho `size` elementos."""
    if size <= 0:
        raise ValueError("size debe ser mayor que 0")
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


def shuffled(items: Iterable[T], rng: random.Random | None = None) -> list[T]:
    """Copia barajada de `items` (acepta un `Random` propio para tests)."""
    data = list(items)
    (rng or random).shuffle(data)
    return data


@dataclass(frozen=True)
class ChanceRoll:
    """Resultado de una tirada de probabilidad."""

    success: bool
    roll: float
    threshold: float


def roll_chance(probability: float, rng: random.Random | None = None) -> ChanceRoll:
    """Tira contra `probability` (0..1) y devuelve el detalle de la tirada."""
    probability = max(0.0, min(1.0, probability))
    value = (rng or random).random()
    return ChanceRoll(success=value < probability, roll=value, threshold=probability)
