"""Panel de administración: estadísticas, economía, baneos y difusión."""
from __future__ import annotations

import asyncio

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import repository as repo
from bot.database.models import utcnow
from bot.games import tournament as tournament_game
from bot.middlewares.auth import AdminMiddleware
from bot.utils.helpers import format_coins

router = Router(name="admin")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())

#: Pausa entre envíos de la difusión para respetar los límites de Telegram.
BROADCAST_DELAY = 0.05

ADMIN_HELP = (
    "🛠️ <b>Panel de administración</b>\n\n"
    "/stats — métricas globales\n"
    "/give &lt;user_id&gt; &lt;cantidad&gt; — dar o quitar monedas\n"
    "/ban &lt;user_id&gt; [motivo] — banear a un jugador\n"
    "/unban &lt;user_id&gt; — levantar el baneo\n"
    "/broadcast &lt;mensaje&gt; — enviar un aviso a todos\n"
    "/addquestion pregunta | op1 | op2 | op3 | op4 | índice_correcto | dificultad\n"
    "/newtournament &lt;nombre&gt; | &lt;cuota&gt; — crear un torneo\n"
    "/finishtournament &lt;id&gt; — cerrar y repartir el bote"
)


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    """Muestra el panel de administración."""
    await message.answer(ADMIN_HELP)


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession) -> None:
    """Métricas globales del bot."""
    stats = await repo.global_stats(session)
    await message.answer(
        "📊 <b>Estadísticas</b>\n\n"
        f"👥 Jugadores: <b>{stats['users']}</b> (baneados: {stats['banned']})\n"
        f"🎮 Partidas jugadas: <b>{stats['games']}</b>\n"
        f"💰 Monedas en circulación: <b>{format_coins(stats['coins'])}</b>\n"
        f"🎰 Total apostado: <b>{format_coins(stats['wagered'])}</b>\n"
        f"🧠 Preguntas de trivia: <b>{stats['questions']}</b>"
    )


@router.message(Command("give"))
async def cmd_give(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    """Añade (o resta, con cantidad negativa) monedas a un jugador."""
    parts = (command.args or "").split()
    if len(parts) != 2:
        await message.answer("Uso: <code>/give &lt;user_id&gt; &lt;cantidad&gt;</code>")
        return
    try:
        user_id, amount = int(parts[0]), int(parts[1])
    except ValueError:
        await message.answer("❌ El ID y la cantidad deben ser números enteros.")
        return

    target = await repo.get_user(session, user_id)
    if target is None:
        await message.answer("❌ Ese jugador no existe.")
        return

    balance = await repo.add_coins(session, target, amount)
    logger.info(f"💸 Admin {message.from_user.id} dio {amount} monedas a {user_id}")
    await message.answer(
        f"✅ {target.display_name} ahora tiene <b>{format_coins(balance)}</b> monedas."
    )


@router.message(Command("ban"))
async def cmd_ban(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    """Banea a un jugador."""
    parts = (command.args or "").split(maxsplit=1)
    if not parts or not parts[0].lstrip("-").isdigit():
        await message.answer("Uso: <code>/ban &lt;user_id&gt; [motivo]</code>")
        return
    user_id = int(parts[0])
    reason = parts[1] if len(parts) > 1 else None
    if not await repo.set_ban(session, user_id, True, reason):
        await message.answer("❌ Ese jugador no existe.")
        return
    logger.warning(f"🚫 Usuario {user_id} baneado por {message.from_user.id}")
    await message.answer(f"🚫 Usuario <code>{user_id}</code> baneado.")


@router.message(Command("unban"))
async def cmd_unban(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    """Levanta el baneo de un jugador."""
    raw = (command.args or "").strip()
    if not raw.lstrip("-").isdigit():
        await message.answer("Uso: <code>/unban &lt;user_id&gt;</code>")
        return
    if not await repo.set_ban(session, int(raw), False):
        await message.answer("❌ Ese jugador no existe.")
        return
    await message.answer(f"✅ Usuario <code>{raw}</code> desbaneado.")


@router.message(Command("broadcast"))
async def cmd_broadcast(
    message: Message, command: CommandObject, session: AsyncSession, bot: Bot
) -> None:
    """Envía un mensaje a todos los jugadores no baneados."""
    text = (command.args or "").strip()
    if not text:
        await message.answer("Uso: <code>/broadcast &lt;mensaje&gt;</code>")
        return

    user_ids = await repo.all_user_ids(session)
    status = await message.answer(f"📣 Enviando a {len(user_ids)} jugadores…")
    sent = failed = 0
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, f"📣 <b>Aviso</b>\n\n{text}")
            sent += 1
        except TelegramAPIError as error:
            failed += 1
            logger.debug(f"Broadcast falló para {user_id}: {error}")
        await asyncio.sleep(BROADCAST_DELAY)

    await status.edit_text(f"📣 Difusión terminada.\n✅ {sent} enviados · ❌ {failed} fallidos")


@router.message(Command("addquestion"))
async def cmd_add_question(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    """Añade una pregunta de trivia.

    Formato: `pregunta | op1 | op2 | op3 | op4 | índice_correcto | dificultad`
    """
    parts = [part.strip() for part in (command.args or "").split("|")]
    if len(parts) < 4:
        await message.answer(
            "Uso: <code>/addquestion pregunta | op1 | op2 | op3 | op4 | "
            "índice_correcto | dificultad</code>"
        )
        return

    difficulty = "easy"
    correct_index = 0
    if len(parts) >= 6 and parts[-1] in {"easy", "medium", "hard"}:
        difficulty = parts[-1]
        parts = parts[:-1]
    if parts[-1].isdigit():
        correct_index = int(parts[-1])
        parts = parts[:-1]

    question, options = parts[0], parts[1:]
    if len(options) < 2:
        await message.answer("❌ Hacen falta al menos dos opciones.")
        return
    if not 0 <= correct_index < len(options):
        await message.answer("❌ El índice correcto está fuera de rango.")
        return

    row = await repo.add_question(
        session,
        question=question,
        options=options,
        correct_index=correct_index,
        difficulty=difficulty,
    )
    await message.answer(
        f"✅ Pregunta <code>#{row.id}</code> añadida "
        f"({difficulty}, respuesta: <b>{options[correct_index]}</b>)."
    )


@router.message(Command("newtournament"))
async def cmd_new_tournament(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    """Crea un torneo abierto a inscripciones."""
    parts = [part.strip() for part in (command.args or "").split("|")]
    if not parts or not parts[0]:
        await message.answer(
            "Uso: <code>/newtournament &lt;nombre&gt; | &lt;cuota&gt;</code>"
        )
        return
    fee = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 100
    tournament = await repo.create_tournament(session, name=parts[0], entry_fee=fee)
    await message.answer(
        f"🏟️ Torneo <b>{tournament.name}</b> creado "
        f"(id <code>{tournament.id}</code>, cuota {format_coins(fee)} 💰)."
    )


@router.message(Command("finishtournament"))
async def cmd_finish_tournament(
    message: Message, command: CommandObject, session: AsyncSession, bot: Bot
) -> None:
    """Cierra un torneo y reparte el bote entre los primeros clasificados."""
    raw = (command.args or "").strip()
    if not raw.isdigit():
        await message.answer("Uso: <code>/finishtournament &lt;id&gt;</code>")
        return

    tournament = await repo.get_tournament(session, int(raw))
    if tournament is None:
        await message.answer("❌ Ese torneo no existe.")
        return
    if tournament.status == "finished":
        await message.answer("❌ Ese torneo ya está cerrado.")
        return

    standings_rows = await repo.tournament_standings(session, tournament.id, limit=100)
    if not tournament_game.can_start(len(standings_rows)):
        await message.answer("❌ No hay participantes suficientes para repartir el bote.")
        return

    standings = tournament_game.build_standings(standings_rows, tournament.prize_pool)
    for standing in standings:
        if standing.prize <= 0:
            continue
        winner = await repo.get_user(session, standing.user_id)
        if winner is None:
            continue
        await repo.add_coins(session, winner, standing.prize)
        try:
            await bot.send_message(
                winner.id,
                f"🏆 El torneo <b>{tournament.name}</b> ha terminado.\n"
                f"Quedaste en la posición <b>{standing.position}</b> y ganas "
                f"<b>{format_coins(standing.prize)}</b> monedas.",
            )
        except TelegramAPIError:
            logger.debug(f"No se pudo avisar al ganador {winner.id}")

    tournament.status = "finished"
    tournament.finished_at = utcnow()
    await message.answer(
        f"🏁 Torneo <b>{tournament.name}</b> cerrado.\n\n"
        f"{tournament_game.render_standings(standings)}"
    )
