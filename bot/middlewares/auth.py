"""Middlewares de sesión, registro de usuario, baneo y anti-flood."""
from __future__ import annotations

import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, User as TgUser
from loguru import logger

from bot.config import settings
from bot.database.db import session_scope
from bot.database.repository import get_or_create_user


class AuthMiddleware(BaseMiddleware):
    """Abre una sesión de BD, registra al usuario y bloquea a los baneados.

    Inyecta en el handler:
      * `session`: `AsyncSession` con transacción abierta (commit al salir).
      * `user`: fila `User` del jugador.
      * `is_admin`: `bool`.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        if tg_user is None or tg_user.is_bot:
            return await handler(event, data)

        async with session_scope() as session:
            user, created = await get_or_create_user(
                session,
                tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                language_code=tg_user.language_code,
            )
            if created:
                logger.info(f"🆕 Nuevo jugador registrado: {tg_user.id} ({tg_user.username})")

            if user.is_banned:
                reason = user.ban_reason or "sin motivo especificado"
                text = f"🚫 Estás baneado del bot.\nMotivo: {reason}"
                if isinstance(event, Message):
                    await event.answer(text)
                elif isinstance(event, CallbackQuery):
                    await event.answer(text, show_alert=True)
                return None

            data["session"] = session
            data["user"] = user
            data["is_new_user"] = created
            data["is_admin"] = settings.is_admin(tg_user.id)
            return await handler(event, data)


class ThrottleMiddleware(BaseMiddleware):
    """Anti-flood sencillo: un evento por usuario cada `cooldown` segundos."""

    def __init__(self, cooldown: float | None = None) -> None:
        self.cooldown = settings.cooldown_seconds if cooldown is None else cooldown
        self._last_seen: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        if tg_user is None or self.cooldown <= 0 or settings.is_admin(tg_user.id):
            return await handler(event, data)

        now = time.monotonic()
        last = self._last_seen.get(tg_user.id, 0.0)
        remaining = self.cooldown - (now - last)
        if remaining > 0:
            if isinstance(event, CallbackQuery):
                await event.answer(
                    f"⏳ Espera {remaining:.1f}s antes de la siguiente acción.",
                    show_alert=False,
                )
            return None

        self._last_seen[tg_user.id] = now
        return await handler(event, data)


class AdminMiddleware(BaseMiddleware):
    """Restringe un router a los IDs listados en `ADMIN_IDS`."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        if tg_user is None or not settings.is_admin(tg_user.id):
            if isinstance(event, Message):
                await event.answer("⛔ Este comando es solo para administradores.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Solo administradores.", show_alert=True)
            return None
        return await handler(event, data)
