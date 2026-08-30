"""Modelos ORM (SQLAlchemy 2.0)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    """`datetime` timezone-aware en UTC (evita `datetime.utcnow()` deprecado)."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base declarativa común."""

    type_annotation_map = {dict: JSON, list: JSON}


class User(Base):
    """Jugador registrado en el bot."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[Optional[str]] = mapped_column(String(64))
    first_name: Mapped[str] = mapped_column(String(128), default="Jugador")
    language_code: Mapped[Optional[str]] = mapped_column(String(8))

    coins: Mapped[int] = mapped_column(Integer, default=0)
    xp: Mapped[int] = mapped_column(Integer, default=0)

    games_played: Mapped[int] = mapped_column(Integer, default=0)
    games_won: Mapped[int] = mapped_column(Integer, default=0)
    total_wagered: Mapped[int] = mapped_column(Integer, default=0)
    best_streak: Mapped[int] = mapped_column(Integer, default=0)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)

    daily_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_daily: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    ban_reason: Mapped[Optional[str]] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    games: Mapped[List["GameRecord"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def display_name(self) -> str:
        if self.username:
            return f"@{self.username}"
        return self.first_name or f"ID {self.id}"

    @property
    def win_rate(self) -> float:
        if not self.games_played:
            return 0.0
        return round(self.games_won / self.games_played * 100, 1)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<User id={self.id} coins={self.coins} xp={self.xp}>"


class GameRecord(Base):
    """Histórico de una partida jugada."""

    __tablename__ = "game_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    game_type: Mapped[str] = mapped_column(String(32), index=True)
    bet: Mapped[int] = mapped_column(Integer, default=0)
    payout: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[str] = mapped_column(String(16), default="lose")  # win | lose | draw
    details: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    user: Mapped["User"] = relationship(back_populates="games")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<GameRecord {self.game_type} {self.result} {self.payout:+d}>"


class TriviaQuestion(Base):
    """Pregunta del juego de trivia."""

    __tablename__ = "trivia_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(32), default="general", index=True)
    difficulty: Mapped[str] = mapped_column(String(16), default="easy", index=True)
    question: Mapped[str] = mapped_column(String(512))
    options: Mapped[list] = mapped_column(JSON, default=list)
    correct_index: Mapped[int] = mapped_column(Integer, default=0)
    reward: Mapped[int] = mapped_column(Integer, default=50)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("question", name="uq_trivia_question"),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<TriviaQuestion {self.id} {self.difficulty}>"


class Tournament(Base):
    """Torneo con inscripción y bote acumulado."""

    __tablename__ = "tournaments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    game_type: Mapped[str] = mapped_column(String(32), default="trivia")
    entry_fee: Mapped[int] = mapped_column(Integer, default=100)
    prize_pool: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    max_players: Mapped[int] = mapped_column(Integer, default=32)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    entries: Mapped[List["TournamentEntry"]] = relationship(
        back_populates="tournament", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Tournament {self.id} {self.name} {self.status}>"


class TournamentEntry(Base):
    """Inscripción de un jugador en un torneo."""

    __tablename__ = "tournament_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tournament_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    score: Mapped[int] = mapped_column(Integer, default=0)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    tournament: Mapped["Tournament"] = relationship(back_populates="entries")
    user: Mapped["User"] = relationship(lazy="selectin")

    __table_args__ = (
        UniqueConstraint("tournament_id", "user_id", name="uq_tournament_player"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<TournamentEntry t={self.tournament_id} u={self.user_id} s={self.score}>"


__all__ = [
    "Base",
    "GameRecord",
    "Tournament",
    "TournamentEntry",
    "TriviaQuestion",
    "User",
    "func",
    "utcnow",
]
