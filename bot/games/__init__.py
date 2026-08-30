"""Games package."""
from . import dice, rps, tournament, trivia
from .base import DRAW, LOSE, WIN, GameOutcome

#: Juegos con apuesta disponibles desde el menú principal.
GAME_LABELS: dict[str, str] = {
    "dice": "🎲 Dados",
    "rps": "✂️ Piedra, papel o tijera",
    "trivia": "🧠 Trivia",
    "tournament": "🏟️ Torneo",
}

__all__ = [
    "DRAW",
    "GAME_LABELS",
    "GameOutcome",
    "LOSE",
    "WIN",
    "dice",
    "rps",
    "tournament",
    "trivia",
]
