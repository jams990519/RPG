"""Comandos de arranque, ayuda y navegación del menú principal."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.database.models import User
from bot.handlers.common import balance_line, edit_or_send, greeting
from bot.keyboards.inline import MenuCB, games_menu_kb, main_menu_kb

router = Router(name="start")

HELP_TEXT = (
    "❓ <b>Ayuda</b>\n\n"
    "🎲 <b>Dados</b> — apuesta a alto/bajo, par/impar o al 6 exacto, "
    "o rétate en un duelo contra el bot.\n"
    "✂️ <b>Piedra, papel o tijera</b> — clásico, x1.95 al ganar y "
    "devolución en empate.\n"
    "🧠 <b>Trivia</b> — no cuesta monedas y las respuestas correctas "
    "suman racha y recompensa.\n"
    "🏟️ <b>Torneos</b> — paga la cuota, acumula puntos y reparte el bote.\n\n"
    "<b>Comandos</b>\n"
    "/start — menú principal\n"
    "/play — elegir juego\n"
    "/profile — tus estadísticas\n"
    "/daily — recompensa diaria\n"
    "/shop — tienda\n"
    "/leaderboard — ranking global\n"
    "/help — esta ayuda"
)


def welcome_text(user: User, is_new: bool) -> str:
    """Texto del menú principal."""
    header = (
        f"🎉 ¡Bienvenido, {greeting(user)}! Te he regalado unas monedas para empezar."
        if is_new
        else f"👋 Hola de nuevo, {greeting(user)}."
    )
    return f"{header}\n\n{balance_line(user)}\n\n¿Qué quieres hacer?"


@router.message(CommandStart())
async def cmd_start(
    message: Message, user: User, state: FSMContext, is_new_user: bool = False
) -> None:
    """Punto de entrada del bot."""
    await state.clear()
    await message.answer(welcome_text(user, is_new_user), reply_markup=main_menu_kb())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Muestra la ayuda."""
    await message.answer(HELP_TEXT, reply_markup=main_menu_kb())


@router.message(Command("menu"))
async def cmd_menu(message: Message, user: User, state: FSMContext) -> None:
    """Vuelve al menú principal."""
    await state.clear()
    await message.answer(welcome_text(user, False), reply_markup=main_menu_kb())


@router.callback_query(MenuCB.filter(F.action == "home"))
async def cb_home(callback: CallbackQuery, user: User, state: FSMContext) -> None:
    """Botón 🏠 Menú."""
    await state.clear()
    await edit_or_send(callback, welcome_text(user, False), main_menu_kb())
    await callback.answer()


@router.callback_query(MenuCB.filter(F.action == "help"))
async def cb_help(callback: CallbackQuery) -> None:
    """Botón ❓ Ayuda."""
    await edit_or_send(callback, HELP_TEXT, main_menu_kb())
    await callback.answer()


@router.callback_query(MenuCB.filter(F.action == "play"))
async def cb_play(callback: CallbackQuery, user: User, state: FSMContext) -> None:
    """Botón 🎮 Jugar: muestra la lista de juegos."""
    await state.clear()
    text = f"🎮 <b>Elige un juego</b>\n\n{balance_line(user)}"
    await edit_or_send(callback, text, games_menu_kb())
    await callback.answer()
