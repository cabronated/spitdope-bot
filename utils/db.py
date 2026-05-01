# utils/db.py
"""
Single SQLite database for all bot data.
Uses aiosqlite for async access so we never block the event loop.
"""

import aiosqlite
from datetime import date, datetime
from typing import Optional

DB_PATH = "spitdope.db"

# ── bootstrap ────────────────────────────────────────────────────────────────

async def init_db() -> None:
    """Create all tables if they don't exist. Call once at bot startup."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            -- Per-guild configuration
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id     INTEGER PRIMARY KEY,
                post_channel INTEGER,
                bars_channel INTEGER,
                role_id      INTEGER,
                daily_time   TEXT    NOT NULL DEFAULT '07:00',
                timezone     TEXT    NOT NULL DEFAULT 'Asia/Kolkata',
                last_post        TEXT,         -- ISO-8601 UTC datetime of last WOTD post
                current_wotd     TEXT,         -- word currently active today
                wotd_action      TEXT NOT NULL DEFAULT 'color',
                                              -- 'color' | 'forward' | 'ping'
                last_leaderboard TEXT          -- ISO-8601 UTC datetime of last leaderboard post
            );

            -- Word queue per guild (ordered by insertion rowid)
            CREATE TABLE IF NOT EXISTS word_queue (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                word     TEXT    NOT NULL,
                UNIQUE(guild_id, word COLLATE NOCASE),
                FOREIGN KEY(guild_id) REFERENCES guild_config(guild_id)
            );

            -- Per-user daily ratebar usage
            CREATE TABLE IF NOT EXISTS ratebar_usage (
                user_id    TEXT    NOT NULL,
                use_date   TEXT    NOT NULL,
                count      INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, use_date)
            );

            -- Every rated verse stored for leaderboard
            CREATE TABLE IF NOT EXISTS verse_scores (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                user_id     TEXT    NOT NULL,
                bar_text    TEXT    NOT NULL,
                score       REAL    NOT NULL,
                had_wotd    INTEGER NOT NULL DEFAULT 0,
                wotd        TEXT,
                scored_date TEXT    NOT NULL,
                scored_at   TEXT    NOT NULL
            );
        """)
        await db.commit()


# ── guild config helpers ──────────────────────────────────────────────────────

async def get_guild_config(guild_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def upsert_guild_config(guild_id: int, **fields) -> None:
    """Insert or update guild config fields."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Ensure row exists
        await db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)", (guild_id,)
        )
        if fields:
            set_clause = ", ".join(f"{k} = ?" for k in fields)
            await db.execute(
                f"UPDATE guild_config SET {set_clause} WHERE guild_id = ?",
                (*fields.values(), guild_id),
            )
        await db.commit()


async def get_all_configured_guilds() -> list[dict]:
    """Return guilds that have all required config set (for the scheduler)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM guild_config
               WHERE post_channel IS NOT NULL
                 AND bars_channel IS NOT NULL
                 AND role_id IS NOT NULL"""
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ── word queue helpers ────────────────────────────────────────────────────────

async def add_words(guild_id: int, words: list[str]) -> int:
    """Insert words, ignoring duplicates. Returns count actually inserted."""
    added = 0
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)", (guild_id,)
        )
        for word in words:
            word = word.strip()
            if not word:
                continue
            cur = await db.execute(
                "INSERT OR IGNORE INTO word_queue (guild_id, word) VALUES (?, ?)",
                (guild_id, word),
            )
            added += cur.rowcount
        await db.commit()
    return added


async def pop_next_word(guild_id: int) -> Optional[str]:
    """Remove and return the oldest word for this guild, or None."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, word FROM word_queue WHERE guild_id = ? ORDER BY id LIMIT 1",
            (guild_id,),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        await db.execute("DELETE FROM word_queue WHERE id = ?", (row[0],))
        await db.commit()
        return row[1]


async def get_words(guild_id: int) -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT word FROM word_queue WHERE guild_id = ? ORDER BY id",
            (guild_id,),
        ) as cur:
            return [r[0] for r in await cur.fetchall()]


async def remove_word(guild_id: int, word: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM word_queue WHERE guild_id = ? AND LOWER(word) = LOWER(?)",
            (guild_id, word),
        )
        await db.commit()
        return cur.rowcount > 0


async def word_count(guild_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM word_queue WHERE guild_id = ?", (guild_id,)
        ) as cur:
            return (await cur.fetchone())[0]


# ── ratebar usage helpers ─────────────────────────────────────────────────────

async def get_usage_count(user_id: int, use_date: date) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT count FROM ratebar_usage WHERE user_id = ? AND use_date = ?",
            (str(user_id), use_date.isoformat()),
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def increment_usage(user_id: int, use_date: date) -> int:
    """Atomically increment usage count and return new value."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO ratebar_usage (user_id, use_date, count) VALUES (?, ?, 1)
               ON CONFLICT(user_id, use_date) DO UPDATE SET count = count + 1""",
            (str(user_id), use_date.isoformat()),
        )
        await db.commit()
        async with db.execute(
            "SELECT count FROM ratebar_usage WHERE user_id = ? AND use_date = ?",
            (str(user_id), use_date.isoformat()),
        ) as cur:
            return (await cur.fetchone())[0]


async def clear_all_usage() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM ratebar_usage")
        await db.commit()


async def get_today_usage(use_date: date) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, count FROM ratebar_usage WHERE use_date = ? ORDER BY count DESC",
            (use_date.isoformat(),),
        ) as cur:
            return [{"user_id": r[0], "count": r[1]} for r in await cur.fetchall()]

# ── verse scores helpers ──────────────────────────────────────────────────────

async def save_verse(
    guild_id: int,
    user_id: int,
    bar_text: str,
    score: float,
    had_wotd: bool,
    wotd: Optional[str],
    scored_date: date,
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO verse_scores
               (guild_id, user_id, bar_text, score, had_wotd, wotd, scored_date, scored_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                guild_id,
                str(user_id),
                bar_text,
                score,
                1 if had_wotd else 0,
                wotd,
                scored_date.isoformat(),
                datetime.utcnow().isoformat(),
            ),
        )
        await db.commit()


async def get_top_verse(
    guild_id: int,
    scored_date: date,
    had_wotd: Optional[bool] = None,
) -> Optional[dict]:
    """
    Get highest scoring verse for a guild on a given date.
    had_wotd=True  -> WOTD verses only
    had_wotd=False -> non-WOTD verses only
    had_wotd=None  -> any verse
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if had_wotd is None:
            query = """SELECT * FROM verse_scores
                       WHERE guild_id = ? AND scored_date = ?
                       ORDER BY score DESC LIMIT 1"""
            params = (guild_id, scored_date.isoformat())
        else:
            query = """SELECT * FROM verse_scores
                       WHERE guild_id = ? AND scored_date = ? AND had_wotd = ?
                       ORDER BY score DESC LIMIT 1"""
            params = (guild_id, scored_date.isoformat(), 1 if had_wotd else 0)

        async with db.execute(query, params) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


# ── current WOTD helper ───────────────────────────────────────────────────────

async def get_current_wotd(guild_id: int) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT current_wotd FROM guild_config WHERE guild_id = ?", (guild_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else None
