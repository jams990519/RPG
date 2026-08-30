"""Carga datos de ejemplo: banco de preguntas y un torneo de bienvenida.

Uso:
    python -m scripts.seed_data
"""
from __future__ import annotations

import asyncio
import random

from loguru import logger

from bot.database.db import dispose_db, init_db, session_scope
from bot.database.repository import bulk_add_questions, create_tournament, open_tournaments
from bot.games.trivia import DEFAULT_QUESTIONS, Question, shuffle_options


def _prepare_questions(rng: random.Random | None = None) -> list[dict]:
    """Baraja las opciones de cada pregunta antes de guardarlas.

    Así el índice correcto no es siempre el 0 y el orden mostrado al jugador
    es estable entre reinicios del bot.
    """
    prepared = []
    for index, raw in enumerate(DEFAULT_QUESTIONS, start=1):
        question = shuffle_options(
            Question(
                id=index,
                question=raw["question"],
                options=tuple(raw["options"]),
                correct_index=raw["correct_index"],
                difficulty=raw["difficulty"],
                category=raw["category"],
            ),
            rng,
        )
        prepared.append(
            {
                "question": question.question,
                "options": list(question.options),
                "correct_index": question.correct_index,
                "difficulty": question.difficulty,
                "category": question.category,
                "reward": question.base_reward,
            }
        )
    return prepared


async def run() -> None:
    """Inserta los datos de ejemplo."""
    await init_db()
    async with session_scope() as session:
        added = await bulk_add_questions(session, _prepare_questions())
        logger.info(f"🧠 {added} preguntas añadidas al banco de trivia")

        if not await open_tournaments(session):
            tournament = await create_tournament(
                session,
                name="Copa de bienvenida",
                game_type="trivia",
                entry_fee=100,
                max_players=16,
            )
            logger.info(f"🏟️ Torneo de ejemplo creado (id {tournament.id})")
    await dispose_db()
    logger.info("✅ Datos de ejemplo cargados")


if __name__ == "__main__":
    asyncio.run(run())
