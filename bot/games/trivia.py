"""Trivia: preguntas de opción múltiple con recompensa por acierto."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Sequence

from bot.games.base import LOSE, WIN, GameOutcome

GAME_TYPE = "trivia"

#: Monedas base por acierto según dificultad.
REWARDS: dict[str, int] = {"easy": 50, "medium": 100, "hard": 200}
XP_REWARDS: dict[str, int] = {"easy": 10, "medium": 20, "hard": 40}

#: Bonificación por racha de aciertos (10% por acierto, máximo x2).
STREAK_BONUS = 0.10
MAX_STREAK_MULTIPLIER = 2.0

OPTION_LABELS = ("🇦", "🇧", "🇨", "🇩")


@dataclass(frozen=True)
class Question:
    """Pregunta lista para jugar, desacoplada del modelo ORM."""

    id: int
    question: str
    options: tuple[str, ...]
    correct_index: int
    difficulty: str = "easy"
    category: str = "general"
    reward: int = 0

    def __post_init__(self) -> None:
        if len(self.options) < 2:
            raise ValueError("Una pregunta necesita al menos 2 opciones")
        if not 0 <= self.correct_index < len(self.options):
            raise ValueError("correct_index fuera de rango")

    @property
    def correct_answer(self) -> str:
        return self.options[self.correct_index]

    @property
    def base_reward(self) -> int:
        return self.reward or REWARDS.get(self.difficulty, REWARDS["easy"])


def from_model(model: Any) -> Question:
    """Convierte una fila `TriviaQuestion` en una `Question`."""
    return Question(
        id=model.id,
        question=model.question,
        options=tuple(model.options),
        correct_index=model.correct_index,
        difficulty=model.difficulty,
        category=model.category,
        reward=model.reward,
    )


def shuffle_options(question: Question, rng: random.Random | None = None) -> Question:
    """Devuelve la misma pregunta con las opciones barajadas."""
    correct = question.correct_answer
    options = list(question.options)
    (rng or random).shuffle(options)
    return Question(
        id=question.id,
        question=question.question,
        options=tuple(options),
        correct_index=options.index(correct),
        difficulty=question.difficulty,
        category=question.category,
        reward=question.reward,
    )


def check_answer(question: Question, chosen_index: int) -> bool:
    """`True` si el índice elegido es el correcto."""
    return chosen_index == question.correct_index


def reward_for(question: Question, streak: int = 0) -> int:
    """Monedas ganadas por acertar, aplicando la bonificación por racha."""
    multiplier = min(MAX_STREAK_MULTIPLIER, 1 + STREAK_BONUS * max(0, streak))
    return int(round(question.base_reward * multiplier))


def evaluate(question: Question, chosen_index: int, *, streak: int = 0) -> GameOutcome:
    """Resuelve la respuesta del jugador.

    La trivia no cuesta monedas: al fallar el `payout` es 0, no negativo.
    """
    correct = check_answer(question, chosen_index)
    payout = reward_for(question, streak) if correct else 0
    chosen = (
        question.options[chosen_index]
        if 0 <= chosen_index < len(question.options)
        else "—"
    )
    text = (
        f"✅ ¡Correcto! La respuesta era <b>{question.correct_answer}</b>."
        if correct
        else (
            f"❌ Fallaste. Respondiste <b>{chosen}</b> y "
            f"la correcta era <b>{question.correct_answer}</b>."
        )
    )
    return GameOutcome(
        game_type=GAME_TYPE,
        result=WIN if correct else LOSE,
        bet=0,
        payout=payout,
        xp=XP_REWARDS.get(question.difficulty, 10) if correct else 2,
        text=text,
        details={
            "question_id": question.id,
            "chosen_index": chosen_index,
            "correct_index": question.correct_index,
            "difficulty": question.difficulty,
            "streak": streak,
        },
    )


def render(question: Question) -> str:
    """Texto HTML de la pregunta con sus opciones etiquetadas."""
    lines = [f"❓ <b>{question.question}</b>", ""]
    for index, option in enumerate(question.options):
        label = OPTION_LABELS[index] if index < len(OPTION_LABELS) else f"{index + 1}."
        lines.append(f"{label} {option}")
    lines.append("")
    lines.append(
        f"🏷️ {question.category} · 🎚️ {question.difficulty} · "
        f"💰 {question.base_reward} monedas"
    )
    return "\n".join(lines)


#: Banco de preguntas por defecto usado por `scripts/seed_data.py`.
DEFAULT_QUESTIONS: Sequence[dict[str, Any]] = (
    {
        "question": "¿Cuál es el planeta más grande del Sistema Solar?",
        "options": ["Júpiter", "Saturno", "Neptuno", "La Tierra"],
        "correct_index": 0,
        "difficulty": "easy",
        "category": "ciencia",
    },
    {
        "question": "¿En qué continente está Egipto?",
        "options": ["África", "Asia", "Europa", "Oceanía"],
        "correct_index": 0,
        "difficulty": "easy",
        "category": "geografía",
    },
    {
        "question": "¿Cuántos lados tiene un hexágono?",
        "options": ["6", "5", "7", "8"],
        "correct_index": 0,
        "difficulty": "easy",
        "category": "matemáticas",
    },
    {
        "question": "¿Quién escribió 'Cien años de soledad'?",
        "options": [
            "Gabriel García Márquez",
            "Mario Vargas Llosa",
            "Julio Cortázar",
            "Pablo Neruda",
        ],
        "correct_index": 0,
        "difficulty": "easy",
        "category": "literatura",
    },
    {
        "question": "¿Cuál es el océano más grande del mundo?",
        "options": ["Pacífico", "Atlántico", "Índico", "Ártico"],
        "correct_index": 0,
        "difficulty": "easy",
        "category": "geografía",
    },
    {
        "question": "¿De qué color es la clorofila?",
        "options": ["Verde", "Rojo", "Azul", "Amarillo"],
        "correct_index": 0,
        "difficulty": "easy",
        "category": "ciencia",
    },
    {
        "question": "¿Cuántos jugadores tiene un equipo de fútbol en el campo?",
        "options": ["11", "10", "9", "12"],
        "correct_index": 0,
        "difficulty": "easy",
        "category": "deportes",
    },
    {
        "question": "¿Cuál es el símbolo químico del oro?",
        "options": ["Au", "Ag", "Or", "Go"],
        "correct_index": 0,
        "difficulty": "medium",
        "category": "ciencia",
    },
    {
        "question": "¿En qué año llegó el ser humano a la Luna?",
        "options": ["1969", "1965", "1972", "1959"],
        "correct_index": 0,
        "difficulty": "medium",
        "category": "historia",
    },
    {
        "question": "¿Cuál es la capital de Australia?",
        "options": ["Canberra", "Sídney", "Melbourne", "Brisbane"],
        "correct_index": 0,
        "difficulty": "medium",
        "category": "geografía",
    },
    {
        "question": "¿Quién pintó 'La noche estrellada'?",
        "options": ["Vincent van Gogh", "Claude Monet", "Pablo Picasso", "Salvador Dalí"],
        "correct_index": 0,
        "difficulty": "medium",
        "category": "arte",
    },
    {
        "question": "¿Cuántos bits tiene un byte?",
        "options": ["8", "4", "16", "32"],
        "correct_index": 0,
        "difficulty": "medium",
        "category": "tecnología",
    },
    {
        "question": "¿Qué lenguaje de programación creó Guido van Rossum?",
        "options": ["Python", "Ruby", "Perl", "Go"],
        "correct_index": 0,
        "difficulty": "medium",
        "category": "tecnología",
    },
    {
        "question": "¿Cuál es el río más largo del mundo?",
        "options": ["Amazonas", "Nilo", "Yangtsé", "Misisipi"],
        "correct_index": 0,
        "difficulty": "medium",
        "category": "geografía",
    },
    {
        "question": "¿En qué año cayó el Muro de Berlín?",
        "options": ["1989", "1991", "1985", "1993"],
        "correct_index": 0,
        "difficulty": "medium",
        "category": "historia",
    },
    {
        "question": "¿Cuál es la unidad de medida de la resistencia eléctrica?",
        "options": ["Ohmio", "Vatio", "Voltio", "Amperio"],
        "correct_index": 0,
        "difficulty": "hard",
        "category": "ciencia",
    },
    {
        "question": "¿Qué algoritmo de ordenación tiene complejidad media O(n log n) y es estable?",
        "options": ["Merge sort", "Quick sort", "Bubble sort", "Selection sort"],
        "correct_index": 0,
        "difficulty": "hard",
        "category": "tecnología",
    },
    {
        "question": "¿Quién formuló el principio de incertidumbre?",
        "options": ["Werner Heisenberg", "Niels Bohr", "Max Planck", "Erwin Schrödinger"],
        "correct_index": 0,
        "difficulty": "hard",
        "category": "ciencia",
    },
    {
        "question": "¿Cuál es la capital de Kazajistán?",
        "options": ["Astaná", "Almatý", "Taskent", "Biskek"],
        "correct_index": 0,
        "difficulty": "hard",
        "category": "geografía",
    },
    {
        "question": "¿En qué año se publicó la primera versión de Linux?",
        "options": ["1991", "1989", "1994", "1987"],
        "correct_index": 0,
        "difficulty": "hard",
        "category": "tecnología",
    },
)
