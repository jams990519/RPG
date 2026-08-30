"""Juego de dados: apuesta al resultado de una tirada de 1 a 6."""
from __future__ import annotations

import random
from typing import Iterable

from bot.games.base import DRAW, LOSE, WIN, GameOutcome, net_payout

GAME_TYPE = "dice"

#: Apuestas disponibles: `clave -> (etiqueta, caras ganadoras, multiplicador)`.
BETS: dict[str, tuple[str, tuple[int, ...], float]] = {
    "low": ("Bajo (1-3)", (1, 2, 3), 1.9),
    "high": ("Alto (4-6)", (4, 5, 6), 1.9),
    "even": ("Par", (2, 4, 6), 1.9),
    "odd": ("Impar", (1, 3, 5), 1.9),
    "six": ("Justo un 6", (6,), 5.5),
}

DICE_FACES = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}


def available_bets() -> Iterable[tuple[str, str, float]]:
    """`(clave, etiqueta, multiplicador)` de cada apuesta, para los teclados."""
    for key, (label, _faces, multiplier) in BETS.items():
        yield key, label, multiplier


def roll(rng: random.Random | None = None) -> int:
    """Tira un dado de seis caras."""
    return (rng or random).randint(1, 6)


def play(choice: str, bet: int, *, value: int | None = None,
         rng: random.Random | None = None) -> GameOutcome:
    """Resuelve una tirada.

    `value` permite reutilizar la tirada real del dado animado de Telegram;
    si es `None` se genera aquí.
    """
    if choice not in BETS:
        raise ValueError(f"Apuesta desconocida: {choice}")
    if bet <= 0:
        raise ValueError("La apuesta debe ser positiva")

    label, winning_faces, multiplier = BETS[choice]
    result_value = value if value is not None else roll(rng)
    if not 1 <= result_value <= 6:
        raise ValueError("El dado debe estar entre 1 y 6")

    won = result_value in winning_faces
    payout = net_payout(bet, multiplier) if won else -bet
    text = (
        f"{DICE_FACES[result_value]} Ha salido un <b>{result_value}</b>.\n"
        f"Apostaste a <b>{label}</b>."
    )
    return GameOutcome(
        game_type=GAME_TYPE,
        result=WIN if won else LOSE,
        bet=bet,
        payout=payout,
        xp=12 if won else 4,
        text=text,
        details={"choice": choice, "value": result_value, "multiplier": multiplier},
    )


def duel(bet: int, rng: random.Random | None = None) -> GameOutcome:
    """Duelo de dados contra el bot: gana la tirada más alta, empate devuelve."""
    if bet <= 0:
        raise ValueError("La apuesta debe ser positiva")
    generator = rng or random
    player, house = roll(generator), roll(generator)
    if player > house:
        result, payout = WIN, net_payout(bet, 2.0)
    elif player < house:
        result, payout = LOSE, -bet
    else:
        result, payout = DRAW, 0
    text = (
        f"Tú {DICE_FACES[player]} <b>{player}</b> vs "
        f"{DICE_FACES[house]} <b>{house}</b> 🤖"
    )
    return GameOutcome(
        game_type=GAME_TYPE,
        result=result,
        bet=bet,
        payout=payout,
        xp=15 if result == WIN else 5,
        text=text,
        details={"mode": "duel", "player": player, "house": house},
    )
