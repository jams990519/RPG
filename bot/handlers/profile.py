"""Perfil, recompensa diaria, ranking y tienda."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import repository as repo
from bot.database.models import User
from bot.games import shop as shop_game
from bot.handlers.common import balance_line, edit_or_send, greeting
from bot.keyboards.inline import (
    MenuCB,
    ShopCB,
    back_home_kb,
    leaderboard_kb,
    profile_kb,
    shop_kb,
)
from bot.utils.helpers import (
    escape,
    format_coins,
    format_timedelta,
    medal,
    progress_bar,
    xp_progress,
)

router = Router(name="profile")

RESULT_EMOJI = {"win": "🟢", "lose": "🔴", "draw": "🟡"}


async def render_profile(session: AsyncSession, user: User) -> str:
    """Ficha completa del jugador."""
    level, current, needed = xp_progress(user.xp)
    rank = await repo.user_rank(session, user, order_by="coins")
    history = await repo.recent_games(session, user.id, limit=5)

    lines = [
        f"👤 <b>{escape(user.display_name)}</b>",
        "",
        f"💰 Monedas: <b>{format_coins(user.coins)}</b>",
        f"⭐ Nivel <b>{level}</b> — {progress_bar(current, needed)} {current}/{needed} XP",
        f"🏅 Puesto global: <b>#{rank}</b>",
        "",
        f"🎮 Partidas: <b>{user.games_played}</b> · "
        f"Victorias: <b>{user.games_won}</b> ({user.win_rate}%)",
        f"🔥 Racha actual: <b>{user.current_streak}</b> · "
        f"Mejor: <b>{user.best_streak}</b>",
        f"🎁 Racha diaria: <b>{user.daily_streak}</b> días",
    ]
    if history:
        lines += ["", "<b>Últimas partidas</b>"]
        for record in history:
            sign = f"{record.payout:+d}" if record.payout else "0"
            lines.append(
                f"{RESULT_EMOJI.get(record.result, '⚪')} {record.game_type} · {sign} 💰"
            )
    return "\n".join(lines)


@router.message(Command("profile"))
async def cmd_profile(message: Message, user: User, session: AsyncSession) -> None:
    """Comando /profile."""
    await message.answer(await render_profile(session, user), reply_markup=profile_kb())


@router.callback_query(MenuCB.filter(F.action == "profile"))
async def cb_profile(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    """Botón 👤 Perfil."""
    await edit_or_send(callback, await render_profile(session, user), profile_kb())
    await callback.answer()


# --------------------------------------------------------------------------- #
# Recompensa diaria
# --------------------------------------------------------------------------- #
async def do_daily(session: AsyncSession, user: User) -> str:
    """Reclama la recompensa diaria y devuelve el mensaje resultante."""
    result = await repo.claim_daily(session, user)
    if not result["claimed"]:
        return (
            "⏳ Ya reclamaste tu recompensa.\n"
            f"Vuelve en <b>{format_timedelta(result['wait'])}</b>.\n\n"
            f"{balance_line(user)}"
        )
    return (
        f"🎁 ¡Toma <b>{format_coins(result['amount'])}</b> monedas, {greeting(user)}!\n"
        f"🔥 Racha diaria: <b>{result['streak']}</b> días\n\n"
        f"{balance_line(user)}"
    )


@router.message(Command("daily"))
async def cmd_daily(message: Message, user: User, session: AsyncSession) -> None:
    """Comando /daily."""
    await message.answer(await do_daily(session, user), reply_markup=profile_kb())


@router.callback_query(MenuCB.filter(F.action == "daily"))
async def cb_daily(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    """Botón 🎁 Diario."""
    await edit_or_send(callback, await do_daily(session, user), profile_kb())
    await callback.answer()


# --------------------------------------------------------------------------- #
# Ranking
# --------------------------------------------------------------------------- #
async def render_leaderboard(session: AsyncSession, order_by: str) -> str:
    """Top 10 de jugadores según el criterio elegido."""
    titles = {"coins": "💰 Monedas", "xp": "⭐ XP", "wins": "🏅 Victorias"}
    players = await repo.top_users(session, order_by=order_by, limit=10)
    if not players:
        return "🏆 Todavía no hay jugadores en el ranking."

    lines = [f"🏆 <b>Ranking — {titles.get(order_by, order_by)}</b>", ""]
    for position, player in enumerate(players, start=1):
        value = {
            "coins": format_coins(player.coins),
            "xp": str(player.xp),
            "wins": str(player.games_won),
        }.get(order_by, format_coins(player.coins))
        lines.append(f"{medal(position)} {escape(player.display_name)} — <b>{value}</b>")
    return "\n".join(lines)


@router.message(Command("leaderboard", "top"))
async def cmd_leaderboard(message: Message, session: AsyncSession) -> None:
    """Comando /leaderboard."""
    await message.answer(
        await render_leaderboard(session, "coins"), reply_markup=leaderboard_kb("coins")
    )


@router.callback_query(MenuCB.filter(F.action == "leaderboard"))
async def cb_leaderboard(callback: CallbackQuery, session: AsyncSession) -> None:
    """Botón 🏆 Ranking."""
    await edit_or_send(
        callback, await render_leaderboard(session, "coins"), leaderboard_kb("coins")
    )
    await callback.answer()


@router.callback_query(MenuCB.filter(F.action == "top"))
async def cb_leaderboard_filter(
    callback: CallbackQuery, callback_data: MenuCB, session: AsyncSession
) -> None:
    """Cambia el criterio del ranking."""
    order_by = callback_data.value or "coins"
    await edit_or_send(
        callback, await render_leaderboard(session, order_by), leaderboard_kb(order_by)
    )
    await callback.answer()


# --------------------------------------------------------------------------- #
# Tienda
# --------------------------------------------------------------------------- #
@router.message(Command("shop"))
async def cmd_shop(message: Message, user: User) -> None:
    """Comando /shop."""
    await message.answer(
        shop_game.render_catalog(user.coins),
        reply_markup=shop_kb(shop_game.catalog()),
    )


@router.callback_query(MenuCB.filter(F.action == "shop"))
async def cb_shop(callback: CallbackQuery, user: User) -> None:
    """Botón 🛒 Tienda."""
    await edit_or_send(
        callback, shop_game.render_catalog(user.coins), shop_kb(shop_game.catalog())
    )
    await callback.answer()


@router.callback_query(ShopCB.filter())
async def cb_buy(
    callback: CallbackQuery,
    callback_data: ShopCB,
    user: User,
    session: AsyncSession,
) -> None:
    """Compra un artículo y aplica su efecto."""
    item = shop_game.get_item(callback_data.item)
    if item is None:
        await callback.answer("❌ Ese artículo ya no está disponible.", show_alert=True)
        return
    if user.coins < item.price:
        await callback.answer("❌ No tienes monedas suficientes.", show_alert=True)
        return

    await repo.add_coins(session, user, -item.price)

    if item.key == "coffee":
        await repo.add_xp(session, user, 150)
        detail = "Has ganado <b>150 XP</b>."
    elif item.key == "chest":
        reward = shop_game.open_chest()
        await repo.add_coins(session, user, reward)
        detail = (
            f"El cofre contenía <b>{format_coins(reward)}</b> monedas."
            if reward
            else "El cofre estaba <b>vacío</b>. 😬"
        )
    else:  # clock
        user.last_daily = None
        detail = "Ya puedes volver a reclamar tu recompensa diaria."

    text = f"✅ Compraste <b>{item.name}</b>.\n{detail}\n\n{balance_line(user)}"
    await edit_or_send(callback, text, back_home_kb())
    await callback.answer("🛍️ ¡Compra realizada!")
