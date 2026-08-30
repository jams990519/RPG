"""Utilidades compartidas por los handlers."""
from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

from bot.database.models import User
from bot.utils.helpers import escape, format_coins, progress_bar, xp_progress


async def edit_or_send(
    callback: CallbackQuery,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
) -> None:
    """Edita el mensaje del callback; si no puede, envía uno nuevo.

    Telegram devuelve `message is not modified` cuando el contenido es idéntico:
    ese caso se ignora porque no es un error real.
    """
    message = callback.message
    if message is None:  # mensaje demasiado antiguo o inaccesible
        return
    try:
        await message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as error:
        if "message is not modified" in str(error):
            return
        await message.answer(text, reply_markup=keyboard)


def balance_line(user: User) -> str:
    """Línea con saldo, nivel y progreso de XP."""
    level, current, needed = xp_progress(user.xp)
    bar = progress_bar(current, needed)
    return (
        f"💰 <b>{format_coins(user.coins)}</b> monedas · "
        f"⭐ Nivel <b>{level}</b>\n{bar} {current}/{needed} XP"
    )


def greeting(user: User) -> str:
    """Saludo con el nombre del jugador ya escapado."""
    return escape(user.first_name or "jugador")
