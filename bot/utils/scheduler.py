"""Tareas programadas (APScheduler)."""
from __future__ import annotations

from datetime import timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
from sqlalchemy import select

from bot.database.db import session_scope
from bot.database.models import User, utcnow
from bot.database.repository import global_stats

#: Solo se avisa a quien haya jugado en los últimos días.
ACTIVE_WINDOW = timedelta(days=7)
DAILY_COOLDOWN = timedelta(hours=24)


async def log_stats() -> None:
    """Deja una foto de las métricas en el log una vez por hora."""
    async with session_scope() as session:
        stats = await global_stats(session)
    logger.info(
        f"📊 {stats['users']} jugadores · {stats['games']} partidas · "
        f"{stats['coins']} monedas en circulación"
    )


async def remind_daily(bot: Bot) -> None:
    """Avisa a los jugadores activos que tienen la recompensa diaria lista."""
    now = utcnow()
    async with session_scope() as session:
        stmt = select(User).where(
            User.is_banned.is_(False),
            User.updated_at >= now - ACTIVE_WINDOW,
            (User.last_daily.is_(None)) | (User.last_daily <= now - DAILY_COOLDOWN),
        )
        users = (await session.scalars(stmt)).all()

    sent = 0
    for user in users:
        try:
            await bot.send_message(
                user.id,
                "🎁 ¡Tu recompensa diaria está lista! Usa /daily para reclamarla.",
            )
            sent += 1
        except TelegramAPIError:
            logger.debug(f"No se pudo recordar el diario a {user.id}")
    if sent:
        logger.info(f"🔔 Recordatorio diario enviado a {sent} jugadores")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Crea el scheduler con las tareas periódicas registradas.

    El scheduler se devuelve **sin arrancar**: lo inicia `main()`.
    """
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(log_stats, "interval", hours=1, id="log_stats")
    scheduler.add_job(
        remind_daily, "cron", hour=18, minute=0, args=[bot], id="remind_daily"
    )
    logger.debug("⏰ Tareas programadas registradas")
    return scheduler
