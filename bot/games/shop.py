"""Tienda: artículos comprables con monedas y su efecto."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterator

GAME_TYPE = "shop"


@dataclass(frozen=True)
class ShopItem:
    """Artículo de la tienda."""

    key: str
    name: str
    price: int
    description: str


ITEMS: dict[str, ShopItem] = {
    "coffee": ShopItem(
        key="coffee",
        name="☕ Café de la suerte",
        price=200,
        description="Te da 150 XP al instante.",
    ),
    "chest": ShopItem(
        key="chest",
        name="🎁 Cofre misterioso",
        price=500,
        description="Contiene entre 0 y 1.500 monedas. ¿Te atreves?",
    ),
    "clock": ShopItem(
        key="clock",
        name="⏰ Reloj de arena",
        price=300,
        description="Reinicia el tiempo de espera de la recompensa diaria.",
    ),
}

#: Premios posibles del cofre y su peso relativo.
CHEST_REWARDS: tuple[tuple[int, int], ...] = (
    (0, 20),
    (250, 30),
    (500, 25),
    (900, 15),
    (1500, 10),
)


def catalog() -> Iterator[tuple[str, str, int]]:
    """`(clave, nombre, precio)` de cada artículo, para construir el teclado."""
    for item in ITEMS.values():
        yield item.key, item.name, item.price


def get_item(key: str) -> ShopItem | None:
    """Busca un artículo por su clave."""
    return ITEMS.get(key)


def open_chest(rng: random.Random | None = None) -> int:
    """Monedas que sale del cofre misterioso."""
    values = [value for value, _weight in CHEST_REWARDS]
    weights = [weight for _value, weight in CHEST_REWARDS]
    return (rng or random).choices(values, weights=weights, k=1)[0]


def render_catalog(balance: int) -> str:
    """Texto HTML del catálogo."""
    lines = ["🛒 <b>Tienda</b>", ""]
    for item in ITEMS.values():
        lines.append(f"<b>{item.name}</b> — {item.price} 💰\n<i>{item.description}</i>")
        lines.append("")
    lines.append(f"Tu saldo: <b>{balance}</b> monedas")
    return "\n".join(lines)
