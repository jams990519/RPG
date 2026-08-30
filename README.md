# 🎮 Telegram Game Bot

Bot de juegos para Telegram construido con **aiogram 3** y **SQLAlchemy 2 (async)**.
Incluye economía de monedas, niveles con XP, rachas, recompensa diaria, tienda,
ranking global, torneos con bote acumulado y panel de administración.

[![CI](https://github.com/jams990519/RPG/actions/workflows/ci.yml/badge.svg)](https://github.com/jams990519/RPG/actions/workflows/ci.yml)

---

## 🕹️ Juegos

| Juego | Cómo funciona | Multiplicador |
|-------|---------------|---------------|
| 🎲 **Dados** | Apuestas a bajo/alto, par/impar o al 6 exacto | ×1.9 · ×5.5 al 6 |
| ⚔️ **Duelo de dados** | Tu tirada contra la del bot, empate devuelve la apuesta | ×2 |
| ✂️ **Piedra, papel o tijera** | Clásico contra el bot | ×1.95 |
| 🧠 **Trivia** | 20 preguntas de ejemplo en 3 dificultades, no cuesta monedas | 50 / 100 / 200 💰 |
| 🏟️ **Torneos** | Cuota de entrada, bote acumulado y reparto 50/30/20 | — |

Extras de la economía:

- **Nivel y XP** — el nivel crece de forma cuadrática (`nivel = √(xp/100) + 1`).
- **Racha** — cada victoria seguida aumenta la recompensa de la trivia hasta ×2.
- **Recompensa diaria** — cada 24 h, con un +10 % por día de racha (máximo ×2).
- **Tienda** — café (XP), cofre misterioso (monedas aleatorias) y reloj de arena
  (reinicia el tiempo de espera del diario).

## ⚡ Puesta en marcha

```bash
git clone https://github.com/jams990519/RPG.git
cd RPG

python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env        # pon tu BOT_TOKEN de @BotFather y tu ADMIN_IDS
python -m scripts.init_db   # crea las tablas
python -m scripts.seed_data # carga el banco de preguntas y un torneo de ejemplo
python main.py
```

### Con Docker

```bash
cp .env.example .env        # rellena BOT_TOKEN
docker compose up -d --build
docker compose logs -f bot
```

La base SQLite y los logs quedan en el volumen `bot_data`. Para usar PostgreSQL:

```bash
docker compose --profile postgres up -d
# y en .env: DATABASE_URL=postgresql://bot:bot@db:5432/bot_db
```

## ⚙️ Configuración

Todas las variables se leen del entorno o de `.env` (ver `.env.example`):

| Variable | Por defecto | Descripción |
|----------|-------------|-------------|
| `BOT_TOKEN` | — | Token de @BotFather (**obligatorio**) |
| `ADMIN_IDS` | vacío | IDs de administradores separados por comas |
| `DATABASE_URL` | `sqlite:///bot_database.db` | Se traduce sola a su driver async |
| `DAILY_COINS` | `100` | Recompensa diaria base |
| `START_COINS` | `500` | Saldo de bienvenida |
| `MIN_BET` / `MAX_BET` | `10` / `10000` | Límites de apuesta |
| `COOLDOWN_SECONDS` | `3` | Anti-flood por usuario (los admins no lo sufren) |
| `LOG_LEVEL` / `LOG_FILE` | `INFO` / `bot.log` | Logging (rotación a 10 MB, 30 días) |
| `DEBUG` | `False` | Activa el `echo` de SQLAlchemy |

## 💬 Comandos

**Jugadores**

| Comando | Qué hace |
|---------|----------|
| `/start` | Menú principal |
| `/play` | Elegir juego |
| `/profile` | Estadísticas, nivel y últimas partidas |
| `/daily` | Recompensa diaria |
| `/shop` | Tienda |
| `/leaderboard` (`/top`) | Ranking por monedas, XP o victorias |
| `/tournaments` | Torneos abiertos |
| `/help` | Ayuda |

**Administradores** (solo los IDs de `ADMIN_IDS`)

| Comando | Qué hace |
|---------|----------|
| `/admin` | Panel de administración |
| `/stats` | Métricas globales |
| `/give <user_id> <cantidad>` | Dar o quitar monedas |
| `/ban <user_id> [motivo]` · `/unban <user_id>` | Moderación |
| `/broadcast <mensaje>` | Aviso a todos los jugadores |
| `/addquestion p \| op1 \| op2 \| op3 \| op4 \| índice \| dificultad` | Nueva pregunta |
| `/newtournament <nombre> \| <cuota>` | Crear torneo |
| `/finishtournament <id>` | Cerrar torneo y repartir el bote |

## 📁 Estructura

```
├── main.py                  # arranque: bot, middlewares, routers, scheduler
├── bot/
│   ├── config.py            # settings (pydantic-settings) y logging
│   ├── handlers/            # start, game, profile, admin (+ common: utilidades)
│   ├── keyboards/inline.py  # teclados y fábricas de callback_data
│   ├── database/            # models, db (engine async), repository (consultas)
│   ├── games/               # lógica pura: base, dice, rps, trivia, tournament, shop
│   ├── middlewares/auth.py  # sesión de BD + registro, baneo, anti-flood, admin
│   └── utils/               # helpers, logger, scheduler
├── scripts/                 # init_db, seed_data
├── tests/                   # tests de lógica, teclados y capa de datos
└── .github/workflows/ci.yml
```

Cómo encaja todo:

1. `AuthMiddleware` abre una `AsyncSession`, registra al jugador y lo inyecta en el
   handler (`session`, `user`, `is_admin`). El commit ocurre al terminar el handler.
2. Los handlers no escriben SQL: usan `bot/database/repository.py`.
3. Los juegos viven en `bot/games/` como **funciones puras** que devuelven un
   `GameOutcome`; eso los hace fáciles de testear sin Telegram ni base de datos.
4. `apply_outcome()` persiste ese resultado (saldo, estadísticas, XP e histórico).

## 🧪 Tests

```bash
pytest          # 55 tests: lógica de juegos, helpers, teclados y capa de datos
```

Los tests de base de datos corren sobre un SQLite temporal creado por la fixture
`session` (`tests/conftest.py`); no hacen falta ni token ni red.

## 📝 Notas sobre las dependencias

- `pydantic` se fija en `2.9.2` porque **aiogram 3.13.1** exige `<2.10`.
- Se retiró `python-telegram-bot-pagination` de `requirements.txt`: pertenece al
  ecosistema de `python-telegram-bot` y no es compatible con aiogram.
- `alembic` y `asyncpg` quedan instalados para migraciones y PostgreSQL; el
  esquema inicial se crea con `scripts/init_db.py`.

## 📄 Licencia

MIT — ver [LICENSE](LICENSE).
