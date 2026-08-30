"""Tests de la capa de datos, los teclados y los helpers."""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database import repository as repo
from bot.database.models import User, utcnow
from bot.games import shop
from bot.games.trivia import DEFAULT_QUESTIONS
from bot.keyboards.inline import (
    BetCB,
    GameCB,
    MenuCB,
    TriviaCB,
    bet_menu_kb,
    dice_options_kb,
    games_menu_kb,
    main_menu_kb,
    rps_moves_kb,
    shop_kb,
)
from bot.utils.helpers import (
    format_coins,
    format_timedelta,
    level_from_xp,
    progress_bar,
    xp_for_level,
    xp_progress,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def test_levels_and_xp_are_consistent() -> None:
    assert level_from_xp(0) == 1
    assert level_from_xp(99) == 1
    assert level_from_xp(100) == 2
    assert level_from_xp(400) == 3
    for level in range(1, 12):
        assert level_from_xp(xp_for_level(level)) == level


def test_xp_progress_reports_position_inside_the_level() -> None:
    level, current, needed = xp_progress(150)
    assert level == 2
    assert current == 50
    assert needed == xp_for_level(3) - xp_for_level(2)


def test_progress_bar_is_fixed_width() -> None:
    assert len(progress_bar(0, 100)) == 10
    assert progress_bar(100, 100) == "▰" * 10
    assert progress_bar(0, 100) == "▱" * 10
    assert len(progress_bar(5, 0, width=4)) == 4


def test_format_helpers() -> None:
    assert format_coins(1234567) == "1.234.567"
    assert format_timedelta(timedelta(hours=2, minutes=5)) == "2h 5m"
    assert format_timedelta(timedelta(seconds=45)) == "45s"
    assert format_timedelta(timedelta(seconds=-10)) == "0s"


# --------------------------------------------------------------------------- #
# Teclados
# --------------------------------------------------------------------------- #
def _callbacks(markup) -> list[str]:
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def test_main_menu_callbacks_are_parseable() -> None:
    for data in _callbacks(main_menu_kb()):
        MenuCB.unpack(data)


def test_games_menu_opens_each_game() -> None:
    games = set()
    for data in _callbacks(games_menu_kb()):
        if data.startswith("game:"):
            games.add(GameCB.unpack(data).game)
    assert {"dice", "rps", "trivia"} <= games


def test_bet_menu_hides_unaffordable_bets() -> None:
    amounts = [
        BetCB.unpack(data).amount
        for data in _callbacks(bet_menu_kb("dice", balance=100))
        if data.startswith("bet:")
    ]
    assert amounts == [10, 50, 100]


def test_dice_and_rps_keyboards_carry_the_bet() -> None:
    for data in _callbacks(dice_options_kb(250)):
        if data.startswith("game:"):
            assert GameCB.unpack(data).bet in (0, 250)
    moves = {
        GameCB.unpack(data).value
        for data in _callbacks(rps_moves_kb(250))
        if data.startswith("game:") and GameCB.unpack(data).action == "move"
    }
    assert moves == {"rock", "paper", "scissors"}


def test_shop_keyboard_lists_the_catalog() -> None:
    labels = _callbacks(shop_kb(shop.catalog()))
    assert sum(1 for data in labels if data.startswith("shop:")) == len(shop.ITEMS)


def test_trivia_callback_roundtrip() -> None:
    packed = TriviaCB(question_id=7, choice=2, streak=4).pack()
    parsed = TriviaCB.unpack(packed)
    assert (parsed.question_id, parsed.choice, parsed.streak) == (7, 2, 4)


# --------------------------------------------------------------------------- #
# Repositorio
# --------------------------------------------------------------------------- #
async def test_get_or_create_user_is_idempotent(session: AsyncSession) -> None:
    user, created = await repo.get_or_create_user(session, 42, username="ana")
    assert created is True
    assert user.coins == settings.start_coins

    same, created_again = await repo.get_or_create_user(session, 42, username="ana2")
    assert created_again is False
    assert same.id == user.id
    assert same.username == "ana2"


async def test_add_coins_never_goes_negative(session: AsyncSession, player: User) -> None:
    assert await repo.add_coins(session, player, -10_000) == 0


async def test_record_game_updates_stats_and_streak(
    session: AsyncSession, player: User
) -> None:
    await repo.record_game(
        session, player, game_type="dice", bet=100, payout=90, result="win", xp=10
    )
    await repo.record_game(
        session, player, game_type="dice", bet=100, payout=90, result="win", xp=10
    )
    await repo.record_game(
        session, player, game_type="dice", bet=100, payout=-100, result="lose", xp=4
    )

    assert player.games_played == 3
    assert player.games_won == 2
    assert player.current_streak == 0
    assert player.best_streak == 2
    assert player.total_wagered == 300
    assert player.coins == 1000 + 90 + 90 - 100
    assert player.win_rate == pytest.approx(66.7)

    history = await repo.recent_games(session, player.id)
    assert len(history) == 3


async def test_claim_daily_respects_the_cooldown(
    session: AsyncSession, player: User
) -> None:
    first = await repo.claim_daily(session, player)
    assert first["claimed"] is True
    assert first["streak"] == 1
    assert player.coins == 1000 + first["amount"]

    second = await repo.claim_daily(session, player)
    assert second["claimed"] is False
    assert second["wait"] > timedelta(0)


async def test_daily_streak_grows_and_resets(session: AsyncSession, player: User) -> None:
    await repo.claim_daily(session, player)
    player.last_daily = utcnow() - timedelta(hours=25)
    second = await repo.claim_daily(session, player)
    assert second["streak"] == 2
    assert second["amount"] > settings.daily_coins

    player.last_daily = utcnow() - timedelta(days=5)
    third = await repo.claim_daily(session, player)
    assert third["streak"] == 1


async def test_ban_and_unban(session: AsyncSession, player: User) -> None:
    assert await repo.set_ban(session, player.id, True, "trampas") is True
    assert player.is_banned is True
    assert player.ban_reason == "trampas"

    assert await repo.set_ban(session, player.id, False) is True
    assert player.is_banned is False
    assert player.ban_reason is None
    assert await repo.set_ban(session, 999_999, True) is False


async def test_leaderboard_orders_and_excludes_banned(session: AsyncSession) -> None:
    for index, coins in enumerate([500, 900, 300], start=1):
        session.add(User(id=index, first_name=f"P{index}", coins=coins, xp=coins))
    session.add(User(id=99, first_name="Baneado", coins=99_999, is_banned=True))
    await session.flush()

    top = await repo.top_users(session, order_by="coins", limit=10)
    assert [user.id for user in top] == [2, 1, 3]

    leader = await repo.get_user(session, 2)
    assert leader is not None
    assert await repo.user_rank(session, leader) == 1

    assert 99 not in await repo.all_user_ids(session)


async def test_bulk_add_questions_skips_duplicates(session: AsyncSession) -> None:
    payload = [
        {
            "question": raw["question"],
            "options": list(raw["options"]),
            "correct_index": raw["correct_index"],
            "difficulty": raw["difficulty"],
            "category": raw["category"],
        }
        for raw in DEFAULT_QUESTIONS
    ]
    assert await repo.bulk_add_questions(session, payload) == len(payload)
    assert await repo.bulk_add_questions(session, payload) == 0

    question = await repo.random_question(session, difficulty="hard")
    assert question is not None
    assert question.difficulty == "hard"


async def test_tournament_join_charges_the_fee(
    session: AsyncSession, player: User
) -> None:
    tournament = await repo.create_tournament(session, name="Copa", entry_fee=250)
    result = await repo.join_tournament(session, tournament, player)
    assert result["ok"] is True
    assert player.coins == 750
    assert tournament.prize_pool == 250

    # No se puede entrar dos veces.
    await session.refresh(tournament)
    again = await repo.join_tournament(session, tournament, player)
    assert again["ok"] is False

    poor = User(id=2002, first_name="Pobre", coins=10)
    session.add(poor)
    await session.flush()
    assert (await repo.join_tournament(session, tournament, poor))["ok"] is False


async def test_tournament_standings_are_sorted(session: AsyncSession) -> None:
    tournament = await repo.create_tournament(session, name="Liga", entry_fee=0)
    for index in range(3):
        user = User(id=3000 + index, first_name=f"J{index}", coins=100)
        session.add(user)
        await session.flush()
        await repo.join_tournament(session, tournament, user)
        await repo.add_tournament_score(session, tournament.id, user.id, index * 10)

    standings = await repo.tournament_standings(session, tournament.id)
    assert [entry.user_id for entry in standings] == [3002, 3001, 3000]


async def test_global_stats_counts_everything(
    session: AsyncSession, player: User
) -> None:
    await repo.record_game(
        session, player, game_type="rps", bet=50, payout=48, result="win"
    )
    stats = await repo.global_stats(session)
    assert stats["users"] == 1
    assert stats["games"] == 1
    assert stats["wagered"] == 50


# --------------------------------------------------------------------------- #
# Tienda
# --------------------------------------------------------------------------- #
def test_shop_chest_returns_a_listed_reward(rng) -> None:
    values = {value for value, _weight in shop.CHEST_REWARDS}
    assert {shop.open_chest(rng) for _ in range(100)} <= values


def test_shop_lookup() -> None:
    assert shop.get_item("chest") is shop.ITEMS["chest"]
    assert shop.get_item("nope") is None
