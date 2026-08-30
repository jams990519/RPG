"""Tests de la lógica pura de los juegos."""
from __future__ import annotations

import pytest

from bot.games import dice, rps
from bot.games.base import DRAW, LOSE, WIN
from bot.games.tournament import distribute_prizes, prize_split
from bot.games.trivia import (
    DEFAULT_QUESTIONS,
    MAX_STREAK_MULTIPLIER,
    REWARDS,
    Question,
    check_answer,
    evaluate,
    render,
    reward_for,
    shuffle_options,
)

SAMPLE = Question(
    id=1,
    question="¿Capital de Francia?",
    options=("París", "Roma", "Berlín", "Madrid"),
    correct_index=0,
    difficulty="medium",
    category="geografía",
)


def test_question_rejects_bad_index() -> None:
    with pytest.raises(ValueError):
        Question(id=1, question="x", options=("a", "b"), correct_index=5)


def test_question_requires_two_options() -> None:
    with pytest.raises(ValueError):
        Question(id=1, question="x", options=("a",), correct_index=0)


def test_shuffle_keeps_the_correct_answer(rng) -> None:
    shuffled = shuffle_options(SAMPLE, rng)
    assert sorted(shuffled.options) == sorted(SAMPLE.options)
    assert shuffled.correct_answer == SAMPLE.correct_answer
    assert shuffled.options[shuffled.correct_index] == "París"


def test_check_answer() -> None:
    assert check_answer(SAMPLE, 0) is True
    assert check_answer(SAMPLE, 2) is False


def test_reward_uses_difficulty_and_streak() -> None:
    assert SAMPLE.base_reward == REWARDS["medium"]
    assert reward_for(SAMPLE, streak=0) == REWARDS["medium"]
    assert reward_for(SAMPLE, streak=3) == int(REWARDS["medium"] * 1.3)
    # La bonificación está limitada a x2.
    assert reward_for(SAMPLE, streak=50) == int(REWARDS["medium"] * MAX_STREAK_MULTIPLIER)


def test_evaluate_correct_answer() -> None:
    outcome = evaluate(SAMPLE, 0, streak=2)
    assert outcome.result == WIN
    assert outcome.payout == reward_for(SAMPLE, 2)
    assert outcome.bet == 0
    assert outcome.details["question_id"] == 1


def test_evaluate_wrong_answer_never_costs_coins() -> None:
    outcome = evaluate(SAMPLE, 3)
    assert outcome.result == LOSE
    assert outcome.payout == 0


def test_render_lists_every_option() -> None:
    text = render(SAMPLE)
    for option in SAMPLE.options:
        assert option in text


def test_default_question_bank_is_consistent() -> None:
    assert len(DEFAULT_QUESTIONS) >= 20
    seen = set()
    for raw in DEFAULT_QUESTIONS:
        assert raw["question"] not in seen, "pregunta duplicada"
        seen.add(raw["question"])
        assert len(raw["options"]) == 4
        assert 0 <= raw["correct_index"] < 4
        assert raw["difficulty"] in REWARDS


# --------------------------------------------------------------------------- #
# Dados
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "choice, value, expected",
    [
        ("low", 2, WIN),
        ("low", 5, LOSE),
        ("high", 6, WIN),
        ("even", 4, WIN),
        ("even", 3, LOSE),
        ("odd", 1, WIN),
        ("six", 6, WIN),
        ("six", 5, LOSE),
    ],
)
def test_dice_resolves_each_bet(choice: str, value: int, expected: str) -> None:
    outcome = dice.play(choice, 100, value=value)
    assert outcome.result == expected


def test_dice_payout_matches_multiplier() -> None:
    win = dice.play("six", 100, value=6)
    assert win.payout == int(round(100 * 5.5)) - 100
    loss = dice.play("six", 100, value=1)
    assert loss.payout == -100


def test_dice_rejects_invalid_input() -> None:
    with pytest.raises(ValueError):
        dice.play("nope", 100, value=1)
    with pytest.raises(ValueError):
        dice.play("low", 0, value=1)
    with pytest.raises(ValueError):
        dice.play("low", 100, value=9)


def test_dice_duel_is_one_of_three_results(rng) -> None:
    results = {dice.duel(50, rng).result for _ in range(200)}
    assert results == {WIN, LOSE, DRAW}


# --------------------------------------------------------------------------- #
# Piedra, papel o tijera
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "player, opponent, expected",
    [
        ("rock", "scissors", WIN),
        ("rock", "paper", LOSE),
        ("rock", "rock", DRAW),
        ("paper", "rock", WIN),
        ("scissors", "paper", WIN),
        ("scissors", "rock", LOSE),
    ],
)
def test_rps_resolution(player: str, opponent: str, expected: str) -> None:
    assert rps.resolve(player, opponent) == expected
    assert rps.play(player, 100, opponent=opponent).result == expected


def test_rps_draw_refunds_the_bet() -> None:
    assert rps.play("rock", 100, opponent="rock").payout == 0


def test_rps_rejects_unknown_move() -> None:
    with pytest.raises(ValueError):
        rps.play("lizard", 100)


# --------------------------------------------------------------------------- #
# Torneos
# --------------------------------------------------------------------------- #
def test_prize_split_shapes() -> None:
    assert prize_split(1) == (1.0,)
    assert len(prize_split(2)) == 2
    assert len(prize_split(9)) == 3


def test_distribute_prizes_never_loses_coins() -> None:
    prizes = distribute_prizes(1000, [1, 2, 3, 4, 5])
    assert [user_id for user_id, _ in prizes] == [1, 2, 3]
    assert sum(prize for _, prize in prizes) == 1000


def test_distribute_prizes_rounds_in_favour_of_the_winner() -> None:
    prizes = distribute_prizes(101, [7, 8, 9])
    assert sum(prize for _, prize in prizes) == 101
    assert prizes[0][1] >= prizes[1][1] >= prizes[2][1]


def test_distribute_prizes_with_empty_pool() -> None:
    assert distribute_prizes(0, [1, 2]) == []
    assert distribute_prizes(500, []) == []
