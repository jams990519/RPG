"""Handlers de los juegos: dados, piedra-papel-tijera, trivia y torneos."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database import repository as repo
from bot.database.models import User
from bot.games import dice as dice_game
from bot.games import rps as rps_game
from bot.games import tournament as tournament_game
from bot.games import trivia as trivia_game
from bot.games.base import GameOutcome
from bot.handlers.common import balance_line, edit_or_send
from bot.keyboards.inline import (
    BetCB,
    GameCB,
    TournamentCB,
    TriviaCB,
    back_home_kb,
    bet_menu_kb,
    dice_options_kb,
    games_menu_kb,
    main_menu_kb,
    play_again_kb,
    rps_moves_kb,
    tournaments_kb,
    trivia_difficulty_kb,
    trivia_question_kb,
)
from bot.utils.helpers import format_coins

router = Router(name="game")


class BetStates(StatesGroup):
    """Estados del flujo de apuesta manual."""

    waiting_amount = State()


BET_PROMPT = (
    "💰 <b>Elige tu apuesta</b>\n\n{balance}\n\n"
    "Apuesta mínima: {min} · máxima: {max}"
)


def validate_bet(amount: int, user: User) -> str | None:
    """Devuelve el motivo del rechazo, o `None` si la apuesta es válida."""
    if amount < settings.min_bet:
        return f"La apuesta mínima es de {format_coins(settings.min_bet)} monedas."
    if amount > settings.max_bet:
        return f"La apuesta máxima es de {format_coins(settings.max_bet)} monedas."
    if amount > user.coins:
        return f"No tienes saldo suficiente (tienes {format_coins(user.coins)})."
    return None


async def apply_outcome(
    session: AsyncSession, user: User, outcome: GameOutcome
) -> str:
    """Guarda el resultado y devuelve el texto que se muestra al jugador."""
    await repo.record_game(
        session,
        user,
        game_type=outcome.game_type,
        bet=outcome.bet,
        payout=outcome.payout,
        result=outcome.result,
        xp=outcome.xp,
        details=outcome.details,
    )
    if outcome.payout > 0:
        summary = f"Ganas <b>+{format_coins(outcome.payout)}</b> monedas."
    elif outcome.payout < 0:
        summary = f"Pierdes <b>{format_coins(abs(outcome.payout))}</b> monedas."
    else:
        summary = "Empate: recuperas tu apuesta."
    return (
        f"{outcome.emoji} {outcome.text}\n\n{summary}\n\n{balance_line(user)}"
    )


# --------------------------------------------------------------------------- #
# Menú de juegos y selección de apuesta
# --------------------------------------------------------------------------- #
@router.message(Command("play"))
async def cmd_play(message: Message, user: User, state: FSMContext) -> None:
    """Comando /play."""
    await state.clear()
    await message.answer(
        f"🎮 <b>Elige un juego</b>\n\n{balance_line(user)}",
        reply_markup=games_menu_kb(),
    )


@router.callback_query(GameCB.filter((F.game.in_({"dice", "rps"})) & (F.action == "open")))
async def cb_open_game(
    callback: CallbackQuery, callback_data: GameCB, user: User, state: FSMContext
) -> None:
    """Abre el selector de apuesta de un juego con apuesta."""
    await state.clear()
    if user.coins < settings.min_bet:
        await edit_or_send(
            callback,
            "😅 Te has quedado sin monedas.\nUsa /daily para reclamar tu recompensa.",
            main_menu_kb(),
        )
        await callback.answer()
        return

    text = BET_PROMPT.format(
        balance=balance_line(user),
        min=format_coins(settings.min_bet),
        max=format_coins(min(settings.max_bet, user.coins)),
    )
    await edit_or_send(callback, text, bet_menu_kb(callback_data.game, user.coins))
    await callback.answer()


@router.callback_query(GameCB.filter(F.action == "custom"))
async def cb_custom_bet(
    callback: CallbackQuery, callback_data: GameCB, state: FSMContext
) -> None:
    """Pide al jugador que escriba la cantidad a apostar."""
    await state.set_state(BetStates.waiting_amount)
    await state.update_data(game=callback_data.game)
    await edit_or_send(
        callback,
        "✏️ Escribe la cantidad que quieres apostar (solo el número).",
        back_home_kb("❌ Cancelar"),
    )
    await callback.answer()


@router.message(BetStates.waiting_amount)
async def on_custom_bet(message: Message, user: User, state: FSMContext) -> None:
    """Procesa la cantidad escrita por el jugador."""
    raw = (message.text or "").strip().replace(".", "").replace(",", "")
    if not raw.isdigit():
        await message.answer("❌ Eso no es un número. Inténtalo de nuevo.")
        return

    amount = int(raw)
    error = validate_bet(amount, user)
    if error:
        await message.answer(f"❌ {error}")
        return

    data = await state.get_data()
    game = str(data.get("game", "dice"))
    await state.clear()
    text, markup = _game_prompt(game, amount)
    await message.answer(text, reply_markup=markup)


def _game_prompt(game: str, bet: int) -> tuple[str, InlineKeyboardMarkup]:
    """Texto y teclado de la pantalla de juego, ya con la apuesta fijada."""
    if game == "rps":
        text = (
            "✂️ <b>Piedra, papel o tijera</b>\n"
            f"Apuesta: <b>{format_coins(bet)}</b> monedas\n\nElige tu jugada:"
        )
        return text, rps_moves_kb(bet)
    text = (
        f"🎲 <b>Dados</b>\nApuesta: <b>{format_coins(bet)}</b> monedas\n\n"
        "¿A qué apuestas?"
    )
    return text, dice_options_kb(bet)


@router.callback_query(BetCB.filter())
async def cb_pick_bet(
    callback: CallbackQuery, callback_data: BetCB, user: User
) -> None:
    """El jugador elige una apuesta rápida."""
    error = validate_bet(callback_data.amount, user)
    if error:
        await callback.answer(f"❌ {error}", show_alert=True)
        return

    text, markup = _game_prompt(callback_data.game, callback_data.amount)
    await edit_or_send(callback, text, markup)
    await callback.answer()


# --------------------------------------------------------------------------- #
# Dados
# --------------------------------------------------------------------------- #
@router.callback_query(GameCB.filter((F.game == "dice") & (F.action.in_({"roll", "duel"}))))
async def cb_dice(
    callback: CallbackQuery,
    callback_data: GameCB,
    user: User,
    session: AsyncSession,
) -> None:
    """Resuelve una partida de dados."""
    bet = callback_data.bet
    error = validate_bet(bet, user)
    if error:
        await callback.answer(f"❌ {error}", show_alert=True)
        return

    if callback_data.action == "duel":
        outcome = dice_game.duel(bet)
    else:
        try:
            outcome = dice_game.play(callback_data.value or "", bet)
        except ValueError as exc:
            logger.warning(f"Apuesta de dados inválida: {exc}")
            await callback.answer("❌ Apuesta no válida.", show_alert=True)
            return

    text = await apply_outcome(session, user, outcome)
    await edit_or_send(callback, text, play_again_kb("dice", bet))
    await callback.answer()


# --------------------------------------------------------------------------- #
# Piedra, papel o tijera
# --------------------------------------------------------------------------- #
@router.callback_query(GameCB.filter((F.game == "rps") & (F.action == "move")))
async def cb_rps(
    callback: CallbackQuery,
    callback_data: GameCB,
    user: User,
    session: AsyncSession,
) -> None:
    """Resuelve una ronda de piedra, papel o tijera."""
    bet = callback_data.bet
    error = validate_bet(bet, user)
    if error:
        await callback.answer(f"❌ {error}", show_alert=True)
        return

    try:
        outcome = rps_game.play(callback_data.value or "", bet)
    except ValueError:
        await callback.answer("❌ Jugada no válida.", show_alert=True)
        return

    text = await apply_outcome(session, user, outcome)
    await edit_or_send(callback, text, play_again_kb("rps", bet))
    await callback.answer()


# --------------------------------------------------------------------------- #
# Trivia
# --------------------------------------------------------------------------- #
@router.callback_query(GameCB.filter((F.game == "trivia") & (F.action == "open")))
async def cb_trivia_menu(callback: CallbackQuery, user: User) -> None:
    """Selector de dificultad."""
    text = (
        "🧠 <b>Trivia</b>\nResponder no cuesta monedas y cada acierto "
        "aumenta tu racha (hasta ×2 de recompensa).\n\n"
        f"Racha actual: <b>{user.current_streak}</b>\n\nElige dificultad:"
    )
    await edit_or_send(callback, text, trivia_difficulty_kb())
    await callback.answer()


@router.callback_query(GameCB.filter((F.game == "trivia") & (F.action == "ask")))
async def cb_trivia_ask(
    callback: CallbackQuery,
    callback_data: GameCB,
    user: User,
    session: AsyncSession,
) -> None:
    """Envía una pregunta aleatoria de la dificultad elegida."""
    difficulty = callback_data.value if callback_data.value in trivia_game.REWARDS else None
    model = await repo.random_question(session, difficulty=difficulty)
    if model is None:
        await edit_or_send(
            callback,
            "😕 No hay preguntas cargadas todavía.\n"
            "Un administrador puede añadirlas con <code>python -m scripts.seed_data</code>.",
            games_menu_kb(),
        )
        await callback.answer()
        return

    question = trivia_game.from_model(model)
    text = (
        f"{trivia_game.render(question)}\n\n"
        f"🔥 Racha: <b>{user.current_streak}</b>"
    )
    await edit_or_send(callback, text, trivia_question_kb(question, user.current_streak))
    await callback.answer()


@router.callback_query(TriviaCB.filter())
async def cb_trivia_answer(
    callback: CallbackQuery,
    callback_data: TriviaCB,
    user: User,
    session: AsyncSession,
) -> None:
    """Corrige la respuesta y aplica la recompensa."""
    model = await repo.get_question(session, callback_data.question_id)
    if model is None:
        await callback.answer("❌ Esa pregunta ya no existe.", show_alert=True)
        return

    question = trivia_game.from_model(model)
    outcome = trivia_game.evaluate(
        question, callback_data.choice, streak=user.current_streak
    )
    text = await apply_outcome(session, user, outcome)
    await edit_or_send(callback, text, play_again_kb("trivia"))
    await callback.answer("✅ ¡Correcto!" if outcome.is_win else "❌ Fallaste")


# --------------------------------------------------------------------------- #
# Torneos
# --------------------------------------------------------------------------- #
@router.message(Command("tournaments"))
async def cmd_tournaments(message: Message, session: AsyncSession) -> None:
    """Lista los torneos abiertos."""
    text, markup = await _tournaments_view(session)
    await message.answer(text, reply_markup=markup)


async def _tournaments_view(
    session: AsyncSession,
) -> tuple[str, InlineKeyboardMarkup]:
    """Construye la vista de torneos abiertos."""
    tournaments = await repo.open_tournaments(session)
    if not tournaments:
        return (
            "🏟️ No hay torneos abiertos ahora mismo.\n"
            "Los administradores pueden crear uno con /newtournament.",
            games_menu_kb(),
        )
    lines = ["🏟️ <b>Torneos abiertos</b>", ""]
    for tournament in tournaments:
        lines.append(
            f"<b>{tournament.name}</b> · {tournament.game_type}\n"
            f"Cuota: {format_coins(tournament.entry_fee)} 💰 · "
            f"Bote: {format_coins(tournament.prize_pool)} 💰 · "
            f"Jugadores: {len(tournament.entries)}/{tournament.max_players}"
        )
    return "\n".join(lines), tournaments_kb(tournaments)


@router.callback_query(TournamentCB.filter(F.action == "list"))
async def cb_tournaments(callback: CallbackQuery, session: AsyncSession) -> None:
    """Botón 🏟️ Torneos."""
    text, markup = await _tournaments_view(session)
    await edit_or_send(callback, text, markup)
    await callback.answer()


@router.callback_query(TournamentCB.filter(F.action == "join"))
async def cb_join_tournament(
    callback: CallbackQuery,
    callback_data: TournamentCB,
    user: User,
    session: AsyncSession,
) -> None:
    """Inscribe al jugador en un torneo."""
    tournament = await repo.get_tournament(session, callback_data.tournament_id)
    if tournament is None:
        await callback.answer("❌ Ese torneo ya no existe.", show_alert=True)
        return

    result = await repo.join_tournament(session, tournament, user)
    if not result["ok"]:
        await callback.answer(f"❌ {result['error']}", show_alert=True)
        return

    standings = await repo.tournament_standings(session, tournament.id)
    text = (
        f"✅ Te has inscrito en <b>{tournament.name}</b>.\n"
        f"Bote actual: <b>{format_coins(tournament.prize_pool)}</b> monedas.\n\n"
        f"{tournament_game.render_standings(tournament_game.build_standings(standings, tournament.prize_pool))}"
        f"\n\n{balance_line(user)}"
    )
    await edit_or_send(callback, text, games_menu_kb())
    await callback.answer("🎟️ ¡Inscripción confirmada!")
