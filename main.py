"""Bot de Juego para Telegram — punto de entrada principal."""
from __future__ import annotations

import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from loguru import logger

from bot.config import settings, setup_logging
from bot.database.db import dispose_db, init_db
from bot.handlers import admin, game, profile, start
from bot.middlewares.auth import AuthMiddleware, ThrottleMiddleware
from bot.utils.scheduler import setup_scheduler

COMMANDS = [
    BotCommand(command="start", description="🎮 Iniciar el bot"),
    BotCommand(command="play", description="🎲 Jugar"),
    BotCommand(command="profile", description="👤 Mi perfil"),
    BotCommand(command="shop", description="🛒 Tienda"),
    BotCommand(command="leaderboard", description="🏆 Ranking"),
    BotCommand(command="daily", description="🎁 Recompensa diaria"),
    BotCommand(command="help", description="❓ Ayuda"),
]


async def main() -> None:
    """Arranca el bot en modo long polling."""
    # 1. Configurar logging
    setup_logging()
    logger.info("🚀 Iniciando bot de juego...")

    if not settings.bot_token:
        logger.error("❌ Falta BOT_TOKEN. Copia .env.example a .env y rellénalo.")
        raise SystemExit(1)

    # 2. Inicializar base de datos
    await init_db()
    logger.info("✅ Base de datos inicializada")

    # 3. Crear bot y dispatcher
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # 4. Registrar middlewares (el anti-flood va antes que el acceso a la BD)
    dp.message.middleware(ThrottleMiddleware())
    dp.callback_query.middleware(ThrottleMiddleware())
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    logger.info("✅ Middlewares registrados")

    # 5. Registrar routers (handlers)
    dp.include_routers(
        admin.router,    # Admin primero (mayor prioridad)
        start.router,
        profile.router,
        game.router,     # Game al final (catch-all)
    )
    logger.info("✅ Handlers registrados")

    # 6. Configurar scheduler (tareas programadas)
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("✅ Scheduler iniciado")

    # 7. Limpiar webhooks y publicar los comandos
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_my_commands(COMMANDS)

    # 8. Iniciar polling
    logger.info("🤖 Bot listo. Esperando mensajes...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await dispose_db()
        logger.info("👋 Bot detenido")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⚠️ Bot detenido por el usuario")
        sys.exit(0)
