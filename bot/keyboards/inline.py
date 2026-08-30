"""Teclados inline y fábricas de `callback_data`."""
from __future__ import annotations

from typing import Iterable, Optional, Sequence

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.games import dice as dice_game
from bot.games import rps as rps_game
from bot.games.trivia import OPTION_LABELS, Question

#: Apuestas rápidas ofrecidas en el menú de apuesta.
QUICK_BETS: tuple[int, ...] = (10, 50, 100, 500, 1000)


class MenuCB(CallbackData, prefix="menu"):
    """Navegación entre las pantallas principales."""

    action: str
    #: Parámetro opcional de la acción (p. ej. el criterio del ranking).
    #: No puede formar parte de `action`: `:` es el separador de aiogram.
    value: Optional[str] = None


class GameCB(CallbackData, prefix="game"):
    """Selección de juego / acción dentro de un juego."""

    game: str
    action: str = "open"
    bet: int = 0
    #: Debe admitir `None`: aiogram serializa los valores vacíos como cadena
    #: vacía y los devuelve como `None` al desempaquetar.
    value: Optional[str] = None


class BetCB(CallbackData, prefix="bet"):
    """Elección de la cantidad apostada para un juego."""

    game: str
    amount: int


class TriviaCB(CallbackData, prefix="trivia"):
    """Respuesta a una pregunta de trivia."""

    question_id: int
    choice: int
    streak: int = 0


class TournamentCB(CallbackData, prefix="tour"):
    """Acciones sobre torneos."""

    action: str
    tournament_id: int = 0


class ShopCB(CallbackData, prefix="shop"):
    """Compra de un artículo de la tienda."""

    item: str


def main_menu_kb() -> InlineKeyboardMarkup:
    """Menú principal del bot."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🎮 Jugar", callback_data=MenuCB(action="play"))
    builder.button(text="👤 Perfil", callback_data=MenuCB(action="profile"))
    builder.button(text="🎁 Diario", callback_data=MenuCB(action="daily"))
    builder.button(text="🛒 Tienda", callback_data=MenuCB(action="shop"))
    builder.button(text="🏆 Ranking", callback_data=MenuCB(action="leaderboard"))
    builder.button(text="❓ Ayuda", callback_data=MenuCB(action="help"))
    builder.adjust(2, 2, 2)
    return builder.as_markup()


def games_menu_kb() -> InlineKeyboardMarkup:
    """Lista de juegos disponibles."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🎲 Dados", callback_data=GameCB(game="dice"))
    builder.button(text="✂️ Piedra/Papel/Tijera", callback_data=GameCB(game="rps"))
    builder.button(text="🧠 Trivia", callback_data=GameCB(game="trivia"))
    builder.button(text="🏟️ Torneos", callback_data=TournamentCB(action="list"))
    builder.button(text="⬅️ Menú", callback_data=MenuCB(action="home"))
    builder.adjust(1, 1, 1, 1, 1)
    return builder.as_markup()


def bet_menu_kb(game: str, balance: int) -> InlineKeyboardMarkup:
    """Botones de apuesta rápida filtrados por el saldo del jugador."""
    builder = InlineKeyboardBuilder()
    affordable = [amount for amount in QUICK_BETS if amount <= balance]
    for amount in affordable:
        builder.button(text=f"💰 {amount}", callback_data=BetCB(game=game, amount=amount))
    builder.button(text="✏️ Otra cantidad", callback_data=GameCB(game=game, action="custom"))
    builder.button(text="⬅️ Juegos", callback_data=MenuCB(action="play"))
    builder.adjust(*([3] * (len(affordable) // 3)), 2 if len(affordable) % 3 else 1, 1)
    return builder.as_markup()


def dice_options_kb(bet: int) -> InlineKeyboardMarkup:
    """Apuestas posibles de la tirada de dados."""
    builder = InlineKeyboardBuilder()
    for key, label, multiplier in dice_game.available_bets():
        builder.button(
            text=f"{label} ×{multiplier}",
            callback_data=GameCB(game="dice", action="roll", bet=bet, value=key),
        )
    builder.button(
        text="⚔️ Duelo contra el bot ×2",
        callback_data=GameCB(game="dice", action="duel", bet=bet),
    )
    builder.button(text="⬅️ Cambiar apuesta", callback_data=GameCB(game="dice"))
    builder.adjust(2, 2, 1, 1, 1)
    return builder.as_markup()


def rps_moves_kb(bet: int) -> InlineKeyboardMarkup:
    """Jugadas de piedra, papel o tijera."""
    builder = InlineKeyboardBuilder()
    for move, label in rps_game.MOVES.items():
        builder.button(
            text=label,
            callback_data=GameCB(game="rps", action="move", bet=bet, value=move),
        )
    builder.button(text="⬅️ Cambiar apuesta", callback_data=GameCB(game="rps"))
    builder.adjust(3, 1)
    return builder.as_markup()


def trivia_difficulty_kb() -> InlineKeyboardMarkup:
    """Selector de dificultad de la trivia."""
    builder = InlineKeyboardBuilder()
    for key, label in (
        ("easy", "🟢 Fácil · 50"),
        ("medium", "🟡 Media · 100"),
        ("hard", "🔴 Difícil · 200"),
    ):
        builder.button(
            text=label,
            callback_data=GameCB(game="trivia", action="ask", value=key),
        )
    builder.button(text="⬅️ Juegos", callback_data=MenuCB(action="play"))
    builder.adjust(1, 1, 1, 1)
    return builder.as_markup()


def trivia_question_kb(question: Question, streak: int = 0) -> InlineKeyboardMarkup:
    """Un botón por opción de respuesta."""
    builder = InlineKeyboardBuilder()
    for index, option in enumerate(question.options):
        label = OPTION_LABELS[index] if index < len(OPTION_LABELS) else str(index + 1)
        builder.button(
            text=f"{label} {option}"[:64],
            callback_data=TriviaCB(
                question_id=question.id, choice=index, streak=streak
            ),
        )
    builder.adjust(1)
    return builder.as_markup()


def play_again_kb(game: str, bet: int = 0) -> InlineKeyboardMarkup:
    """Repetir partida o volver al menú."""
    builder = InlineKeyboardBuilder()
    if game == "trivia":
        builder.button(
            text="🔁 Otra pregunta",
            callback_data=GameCB(game="trivia", action="ask", value="any"),
        )
    else:
        builder.button(
            text="🔁 Repetir apuesta",
            callback_data=BetCB(game=game, amount=bet),
        )
        builder.button(text="💰 Cambiar apuesta", callback_data=GameCB(game=game))
    builder.button(text="🎮 Juegos", callback_data=MenuCB(action="play"))
    builder.button(text="🏠 Menú", callback_data=MenuCB(action="home"))
    builder.adjust(2, 2)
    return builder.as_markup()


def profile_kb() -> InlineKeyboardMarkup:
    """Acciones desde la pantalla de perfil."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🎁 Recompensa diaria", callback_data=MenuCB(action="daily"))
    builder.button(text="🏆 Ranking", callback_data=MenuCB(action="leaderboard"))
    builder.button(text="🎮 Jugar", callback_data=MenuCB(action="play"))
    builder.button(text="🏠 Menú", callback_data=MenuCB(action="home"))
    builder.adjust(1, 1, 2)
    return builder.as_markup()


def leaderboard_kb(current: str = "coins") -> InlineKeyboardMarkup:
    """Cambia el criterio del ranking."""
    builder = InlineKeyboardBuilder()
    for key, label in (("coins", "💰 Monedas"), ("xp", "⭐ XP"), ("wins", "🏅 Victorias")):
        mark = "• " if key == current else ""
        builder.button(
            text=f"{mark}{label}",
            callback_data=MenuCB(action="top", value=key),
        )
    builder.button(text="🏠 Menú", callback_data=MenuCB(action="home"))
    builder.adjust(3, 1)
    return builder.as_markup()


def shop_kb(items: Iterable[tuple[str, str, int]]) -> InlineKeyboardMarkup:
    """Artículos comprables: `(clave, nombre, precio)`."""
    builder = InlineKeyboardBuilder()
    for key, name, price in items:
        builder.button(text=f"{name} · {price} 💰", callback_data=ShopCB(item=key))
    builder.button(text="🏠 Menú", callback_data=MenuCB(action="home"))
    builder.adjust(1)
    return builder.as_markup()


def tournaments_kb(tournaments: Sequence[object]) -> InlineKeyboardMarkup:
    """Lista de torneos abiertos con botón de inscripción."""
    builder = InlineKeyboardBuilder()
    for tournament in tournaments:
        builder.button(
            text=f"🏟️ {tournament.name} · {tournament.entry_fee} 💰",  # type: ignore[attr-defined]
            callback_data=TournamentCB(action="join", tournament_id=tournament.id),  # type: ignore[attr-defined]
        )
    builder.button(text="⬅️ Juegos", callback_data=MenuCB(action="play"))
    builder.adjust(1)
    return builder.as_markup()


def back_home_kb(text: str = "🏠 Menú") -> InlineKeyboardMarkup:
    """Teclado de un solo botón para volver al menú principal."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=MenuCB(action="home").pack())]
        ]
    )
