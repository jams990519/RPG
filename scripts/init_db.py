"""Crea (o recrea) el esquema de la base de datos.

Uso:
    python -m scripts.init_db
    python -m scripts.init_db --drop   # ⚠️ borra todos los datos
"""
from __future__ import annotations

import argparse
import asyncio

from loguru import logger

from bot.config import settings
from bot.database.db import dispose_db, init_db


async def run(drop: bool) -> None:
    """Ejecuta la creación del esquema."""
    if drop:
        logger.warning("⚠️ Se van a borrar todas las tablas existentes")
    await init_db(drop_all=drop)
    await dispose_db()
    logger.info(f"✅ Esquema listo en {settings.database_url}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inicializa la base de datos del bot")
    parser.add_argument(
        "--drop", action="store_true", help="borra las tablas antes de crearlas"
    )
    args = parser.parse_args()
    asyncio.run(run(args.drop))


if __name__ == "__main__":
    main()
