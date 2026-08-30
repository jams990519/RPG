"""Lógica de torneos: inscripción, puntuación y reparto de premios."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

GAME_TYPE = "tournament"

MIN_PLAYERS = 2

#: Reparto del bote según cuántos jugadores premiados haya.
PRIZE_SPLITS: dict[int, tuple[float, ...]] = {
    1: (1.0,),
    2: (0.65, 0.35),
    3: (0.5, 0.3, 0.2),
}


@dataclass(frozen=True)
class Standing:
    """Una posición de la clasificación."""

    position: int
    user_id: int
    name: str
    score: int
    prize: int = 0


def prize_split(players: int) -> tuple[float, ...]:
    """Porcentajes de reparto para un número dado de jugadores."""
    if players <= 0:
        return ()
    return PRIZE_SPLITS.get(min(players, 3), PRIZE_SPLITS[3])


def distribute_prizes(prize_pool: int, player_ids: Sequence[int]) -> list[tuple[int, int]]:
    """Reparte el bote entre los primeros clasificados.

    Devuelve `[(user_id, premio)]`. El redondeo sobrante se le da al primero,
    de forma que la suma de premios es siempre exactamente `prize_pool`.
    """
    if prize_pool <= 0 or not player_ids:
        return []
    splits = prize_split(len(player_ids))
    winners = list(player_ids[: len(splits)])
    prizes = [int(prize_pool * share) for share in splits]
    prizes[0] += prize_pool - sum(prizes)
    return list(zip(winners, prizes))


def can_start(player_count: int) -> bool:
    """`True` si hay jugadores suficientes para cerrar el torneo."""
    return player_count >= MIN_PLAYERS


def build_standings(
    entries: Sequence[object], prize_pool: int = 0
) -> list[Standing]:
    """Construye la clasificación a partir de filas `TournamentEntry`.

    Las entradas deben venir ya ordenadas por puntuación descendente.
    """
    ordered = list(entries)
    prizes = dict(
        distribute_prizes(prize_pool, [entry.user_id for entry in ordered])  # type: ignore[attr-defined]
    )
    standings: list[Standing] = []
    for position, entry in enumerate(ordered, start=1):
        user = getattr(entry, "user", None)
        name = getattr(user, "display_name", None) or f"ID {entry.user_id}"  # type: ignore[attr-defined]
        standings.append(
            Standing(
                position=position,
                user_id=entry.user_id,  # type: ignore[attr-defined]
                name=name,
                score=entry.score,  # type: ignore[attr-defined]
                prize=prizes.get(entry.user_id, 0),  # type: ignore[attr-defined]
            )
        )
    return standings


def render_standings(standings: Sequence[Standing]) -> str:
    """Texto HTML de la clasificación."""
    if not standings:
        return "Todavía no hay participantes."
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = []
    for standing in standings:
        prefix = medals.get(standing.position, f"{standing.position}.")
        prize = f" · 💰 {standing.prize}" if standing.prize else ""
        lines.append(f"{prefix} {standing.name} — {standing.score} pts{prize}")
    return "\n".join(lines)
