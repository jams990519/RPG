"""Piedra, papel o tijera contra el bot."""
from __future__ import annotations

import random

from bot.games.base import DRAW, LOSE, WIN, GameOutcome, net_payout

GAME_TYPE = "rps"

MOVES: dict[str, str] = {
    "rock": "🪨 Piedra",
    "paper": "📄 Papel",
    "scissors": "✂️ Tijera",
}

#: Cada jugada gana contra la indicada aquí.
BEATS: dict[str, str] = {
    "rock": "scissors",
    "paper": "rock",
    "scissors": "paper",
}

WIN_MULTIPLIER = 1.95


def bot_move(rng: random.Random | None = None) -> str:
    """Jugada aleatoria del bot."""
    return (rng or random).choice(list(MOVES))


def resolve(player: str, opponent: str) -> str:
    """Devuelve `win`, `lose` o `draw` desde la perspectiva del jugador."""
    if player not in MOVES or opponent not in MOVES:
        raise ValueError("Jugada inválida")
    if player == opponent:
        return DRAW
    return WIN if BEATS[player] == opponent else LOSE


def play(player: str, bet: int, *, opponent: str | None = None,
         rng: random.Random | None = None) -> GameOutcome:
    """Juega una ronda contra el bot y devuelve el resultado."""
    if bet <= 0:
        raise ValueError("La apuesta debe ser positiva")
    if player not in MOVES:
        raise ValueError(f"Jugada desconocida: {player}")

    rival = opponent if opponent is not None else bot_move(rng)
    result = resolve(player, rival)
    if result == WIN:
        payout = net_payout(bet, WIN_MULTIPLIER)
    elif result == LOSE:
        payout = -bet
    else:
        payout = 0

    text = f"{MOVES[player]}  vs  {MOVES[rival]} 🤖"
    return GameOutcome(
        game_type=GAME_TYPE,
        result=result,
        bet=bet,
        payout=payout,
        xp={WIN: 15, DRAW: 6, LOSE: 4}[result],
        text=text,
        details={"player": player, "opponent": rival},
    )
