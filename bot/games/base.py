"""Tipos comunes a todos los juegos."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

WIN = "win"
LOSE = "lose"
DRAW = "draw"


@dataclass(frozen=True)
class GameOutcome:
    """Resultado de una partida, independiente de Telegram y de la BD.

    `payout` es el neto en monedas: `+X` si el jugador gana, `-bet` si pierde
    y `0` en empate (se le devuelve la apuesta).
    """

    game_type: str
    result: str
    bet: int
    payout: int
    xp: int = 0
    text: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_win(self) -> bool:
        return self.result == WIN

    @property
    def is_draw(self) -> bool:
        return self.result == DRAW

    @property
    def emoji(self) -> str:
        return {WIN: "🎉", LOSE: "💀", DRAW: "🤝"}[self.result]


def net_payout(bet: int, multiplier: float) -> int:
    """Neto que se abona al jugador al ganar con un multiplicador dado."""
    return int(round(bet * multiplier)) - bet


__all__ = ["DRAW", "LOSE", "WIN", "GameOutcome", "net_payout"]
