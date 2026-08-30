"""Operaciones de alto nivel sobre la base de datos.

Los handlers nunca escriben SQL: usan estas funciones, que reciben siempre
una `AsyncSession` abierta por el llamante (normalmente vía `session_scope`).
"""
from __future__ import annotations

import random
from datetime import timedelta
from typing import Any, Optional, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import (
    GameRecord,
    Tournament,
    TournamentEntry,
    TriviaQuestion,
    User,
    utcnow,
)
from bot.utils.helpers import level_from_xp

DAILY_COOLDOWN = timedelta(hours=24)
#: Pasado este margen sin reclamar, la racha diaria se reinicia.
DAILY_STREAK_GRACE = timedelta(hours=48)


# --------------------------------------------------------------------------- #
# Usuarios
# --------------------------------------------------------------------------- #
async def get_user(session: AsyncSession, user_id: int) -> Optional[User]:
    """Busca un usuario por su ID de Telegram."""
    return await session.get(User, user_id)


async def get_or_create_user(
    session: AsyncSession,
    user_id: int,
    *,
    username: str | None = None,
    first_name: str | None = None,
    language_code: str | None = None,
) -> tuple[User, bool]:
    """Devuelve `(usuario, creado)` registrándolo si es su primera vez."""
    user = await session.get(User, user_id)
    if user is not None:
        changed = False
        if username != user.username:
            user.username, changed = username, True
        if first_name and first_name != user.first_name:
            user.first_name, changed = first_name, True
        if changed:
            user.updated_at = utcnow()
        return user, False

    user = User(
        id=user_id,
        username=username,
        first_name=first_name or "Jugador",
        language_code=language_code,
        coins=settings.start_coins,
    )
    session.add(user)
    await session.flush()
    return user, True


async def add_coins(session: AsyncSession, user: User, amount: int) -> int:
    """Suma (o resta) monedas sin permitir saldo negativo. Devuelve el saldo."""
    user.coins = max(0, user.coins + amount)
    user.updated_at = utcnow()
    await session.flush()
    return user.coins


async def add_xp(session: AsyncSession, user: User, amount: int) -> tuple[int, bool]:
    """Suma XP. Devuelve `(nivel_actual, ha_subido_de_nivel)`."""
    before = level_from_xp(user.xp)
    user.xp = max(0, user.xp + amount)
    after = level_from_xp(user.xp)
    user.updated_at = utcnow()
    await session.flush()
    return after, after > before


async def record_game(
    session: AsyncSession,
    user: User,
    *,
    game_type: str,
    bet: int,
    payout: int,
    result: str,
    xp: int = 0,
    details: dict[str, Any] | None = None,
) -> GameRecord:
    """Registra una partida y actualiza saldo, estadísticas y XP del jugador.

    `payout` es el resultado neto: positivo si el jugador gana monedas,
    negativo si las pierde.
    """
    user.games_played += 1
    user.total_wagered += max(0, bet)
    if result == "win":
        user.games_won += 1
        user.current_streak += 1
        user.best_streak = max(user.best_streak, user.current_streak)
    elif result == "lose":
        user.current_streak = 0

    await add_coins(session, user, payout)
    if xp:
        await add_xp(session, user, xp)

    record = GameRecord(
        user_id=user.id,
        game_type=game_type,
        bet=bet,
        payout=payout,
        result=result,
        details=details or {},
    )
    session.add(record)
    await session.flush()
    return record


async def claim_daily(session: AsyncSession, user: User) -> dict[str, Any]:
    """Intenta reclamar la recompensa diaria.

    Devuelve `{"claimed": bool, "amount": int, "streak": int, "wait": timedelta}`.
    """
    now = utcnow()
    last = user.last_daily
    if last is not None and last.tzinfo is None:
        last = last.replace(tzinfo=now.tzinfo)

    if last is not None and now - last < DAILY_COOLDOWN:
        return {
            "claimed": False,
            "amount": 0,
            "streak": user.daily_streak,
            "wait": DAILY_COOLDOWN - (now - last),
        }

    if last is not None and now - last <= DAILY_STREAK_GRACE:
        user.daily_streak += 1
    else:
        user.daily_streak = 1

    # Bonificación del 10% por día de racha, hasta duplicar la recompensa.
    multiplier = min(2.0, 1 + 0.1 * (user.daily_streak - 1))
    amount = int(settings.daily_coins * multiplier)

    user.last_daily = now
    await add_coins(session, user, amount)
    await add_xp(session, user, 10)

    return {"claimed": True, "amount": amount, "streak": user.daily_streak, "wait": timedelta()}


async def set_ban(
    session: AsyncSession, user_id: int, banned: bool, reason: str | None = None
) -> bool:
    """Banea o desbanea a un usuario. Devuelve `False` si no existe."""
    user = await session.get(User, user_id)
    if user is None:
        return False
    user.is_banned = banned
    user.ban_reason = reason if banned else None
    user.updated_at = utcnow()
    await session.flush()
    return True


async def top_users(
    session: AsyncSession, *, order_by: str = "coins", limit: int = 10
) -> Sequence[User]:
    """Ranking de jugadores por `coins`, `xp` o `games_won`."""
    column = {
        "coins": User.coins,
        "xp": User.xp,
        "wins": User.games_won,
        "games_won": User.games_won,
        "streak": User.best_streak,
    }.get(order_by, User.coins)
    stmt = (
        select(User)
        .where(User.is_banned.is_(False))
        .order_by(column.desc(), User.id.asc())
        .limit(limit)
    )
    return (await session.scalars(stmt)).all()


async def user_rank(session: AsyncSession, user: User, *, order_by: str = "coins") -> int:
    """Posición del usuario en el ranking (1-indexado)."""
    column = {"coins": User.coins, "xp": User.xp, "wins": User.games_won}.get(
        order_by, User.coins
    )
    value = getattr(user, column.key)
    stmt = select(func.count()).select_from(User).where(
        User.is_banned.is_(False), column > value
    )
    return int(await session.scalar(stmt) or 0) + 1


async def all_user_ids(session: AsyncSession) -> Sequence[int]:
    """IDs de todos los usuarios activos (para difusión de mensajes)."""
    stmt = select(User.id).where(User.is_banned.is_(False))
    return (await session.scalars(stmt)).all()


async def global_stats(session: AsyncSession) -> dict[str, int]:
    """Métricas agregadas para el panel de administración."""
    users = int(await session.scalar(select(func.count()).select_from(User)) or 0)
    banned = int(
        await session.scalar(
            select(func.count()).select_from(User).where(User.is_banned.is_(True))
        )
        or 0
    )
    games = int(await session.scalar(select(func.count()).select_from(GameRecord)) or 0)
    coins = int(await session.scalar(select(func.coalesce(func.sum(User.coins), 0))) or 0)
    wagered = int(
        await session.scalar(select(func.coalesce(func.sum(GameRecord.bet), 0))) or 0
    )
    questions = int(
        await session.scalar(select(func.count()).select_from(TriviaQuestion)) or 0
    )
    return {
        "users": users,
        "banned": banned,
        "games": games,
        "coins": coins,
        "wagered": wagered,
        "questions": questions,
    }


async def recent_games(
    session: AsyncSession, user_id: int, limit: int = 5
) -> Sequence[GameRecord]:
    """Últimas partidas de un jugador, de la más reciente a la más antigua."""
    stmt = (
        select(GameRecord)
        .where(GameRecord.user_id == user_id)
        .order_by(GameRecord.created_at.desc(), GameRecord.id.desc())
        .limit(limit)
    )
    return (await session.scalars(stmt)).all()


# --------------------------------------------------------------------------- #
# Trivia
# --------------------------------------------------------------------------- #
async def random_question(
    session: AsyncSession,
    *,
    difficulty: str | None = None,
    category: str | None = None,
    rng: random.Random | None = None,
) -> Optional[TriviaQuestion]:
    """Pregunta aleatoria activa que cumpla los filtros dados."""
    stmt = select(TriviaQuestion).where(TriviaQuestion.is_active.is_(True))
    if difficulty:
        stmt = stmt.where(TriviaQuestion.difficulty == difficulty)
    if category:
        stmt = stmt.where(TriviaQuestion.category == category)
    questions = (await session.scalars(stmt)).all()
    if not questions:
        return None
    return (rng or random).choice(list(questions))


async def get_question(session: AsyncSession, question_id: int) -> Optional[TriviaQuestion]:
    """Recupera una pregunta por ID."""
    return await session.get(TriviaQuestion, question_id)


async def add_question(session: AsyncSession, **fields: Any) -> TriviaQuestion:
    """Inserta una pregunta nueva en el banco de trivia."""
    question = TriviaQuestion(**fields)
    session.add(question)
    await session.flush()
    return question


async def bulk_add_questions(
    session: AsyncSession, payload: list[dict[str, Any]]
) -> int:
    """Inserta preguntas ignorando las que ya existen. Devuelve cuántas añadió."""
    existing = set((await session.scalars(select(TriviaQuestion.question))).all())
    added = 0
    for item in payload:
        if item["question"] in existing:
            continue
        session.add(TriviaQuestion(**item))
        existing.add(item["question"])
        added += 1
    await session.flush()
    return added


# --------------------------------------------------------------------------- #
# Torneos
# --------------------------------------------------------------------------- #
async def create_tournament(session: AsyncSession, **fields: Any) -> Tournament:
    """Crea un torneo abierto a inscripciones."""
    tournament = Tournament(**fields)
    session.add(tournament)
    await session.flush()
    return tournament


async def open_tournaments(session: AsyncSession) -> Sequence[Tournament]:
    """Torneos que todavía admiten inscripciones."""
    stmt = select(Tournament).where(Tournament.status == "open").order_by(Tournament.id)
    return (await session.scalars(stmt)).all()


async def get_tournament(session: AsyncSession, tournament_id: int) -> Optional[Tournament]:
    """Recupera un torneo por ID."""
    return await session.get(Tournament, tournament_id)


async def join_tournament(
    session: AsyncSession, tournament: Tournament, user: User
) -> dict[str, Any]:
    """Inscribe al jugador cobrando la cuota. Devuelve `{"ok", "error"}`."""
    if tournament.status != "open":
        return {"ok": False, "error": "El torneo ya no admite inscripciones."}

    # Se consulta explícitamente en lugar de recorrer `tournament.entries`:
    # la colección puede estar expirada y su carga perezosa no es válida
    # dentro de una sesión asíncrona.
    players = int(
        await session.scalar(
            select(func.count())
            .select_from(TournamentEntry)
            .where(TournamentEntry.tournament_id == tournament.id)
        )
        or 0
    )
    if players >= tournament.max_players:
        return {"ok": False, "error": "El torneo está completo."}

    already_in = await session.scalar(
        select(TournamentEntry.id).where(
            TournamentEntry.tournament_id == tournament.id,
            TournamentEntry.user_id == user.id,
        )
    )
    if already_in is not None:
        return {"ok": False, "error": "Ya estás inscrito en este torneo."}
    if user.coins < tournament.entry_fee:
        return {"ok": False, "error": "No tienes monedas suficientes para la cuota."}

    await add_coins(session, user, -tournament.entry_fee)
    tournament.prize_pool += tournament.entry_fee
    entry = TournamentEntry(tournament_id=tournament.id, user_id=user.id)
    session.add(entry)
    await session.flush()
    return {"ok": True, "error": None, "entry": entry}


async def add_tournament_score(
    session: AsyncSession, tournament_id: int, user_id: int, points: int
) -> None:
    """Suma puntos a la inscripción de un jugador."""
    await session.execute(
        update(TournamentEntry)
        .where(
            TournamentEntry.tournament_id == tournament_id,
            TournamentEntry.user_id == user_id,
        )
        .values(score=TournamentEntry.score + points)
    )
    await session.flush()


async def tournament_standings(
    session: AsyncSession, tournament_id: int, limit: int = 10
) -> Sequence[TournamentEntry]:
    """Clasificación ordenada por puntuación descendente."""
    stmt = (
        select(TournamentEntry)
        .where(TournamentEntry.tournament_id == tournament_id)
        .order_by(TournamentEntry.score.desc(), TournamentEntry.joined_at.asc())
        .limit(limit)
    )
    return (await session.scalars(stmt)).all()
