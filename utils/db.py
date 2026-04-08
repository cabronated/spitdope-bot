# utils/db.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import asyncio
from typing import List, Tuple, Optional

def get_conn():
    return psycopg2.connect(
        dbname=os.getenv("PG_DB"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASS"),
        host=os.getenv("PG_HOST"),
        port=int(os.getenv("PG_PORT", 5432))
    )

# --- Synchronous helpers (run in thread) ---

def _create_tables_sync():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS words (
        id SERIAL PRIMARY KEY,
        word TEXT NOT NULL,
        language TEXT NOT NULL DEFAULT 'english',
        added_by BIGINT,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    cur.close()
    conn.close()

def _add_word_sync(word: str, language: str, user_id: Optional[int]):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO words (word, language, added_by) VALUES (%s, %s, %s)",
        (word, language, user_id)
    )
    conn.commit()
    cur.close()
    conn.close()

def _get_words_sync(limit: int = 200) -> List[Tuple]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, word, language, added_by, added_at FROM words ORDER BY id ASC LIMIT %s", (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def _get_word_count_sync() -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM words")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count

def _pop_next_word_sync() -> Optional[Tuple]:
    """
    Fetch and delete the oldest word (FIFO). Returns the row (id, word, language, added_by, added_at) or None.
    """
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, word, language, added_by, added_at FROM words ORDER BY id ASC LIMIT 1")
    row = cur.fetchone()
    if row:
        cur.execute("DELETE FROM words WHERE id = %s", (row["id"],))
        conn.commit()
    cur.close()
    conn.close()
    return row

# --- Async wrappers ---

async def create_tables():
    await asyncio.to_thread(_create_tables_sync)

async def add_word(word: str, language: str = "english", user_id: Optional[int] = None):
    await asyncio.to_thread(_add_word_sync, word, language, user_id)

async def get_words(limit: int = 200):
    return await asyncio.to_thread(_get_words_sync, limit)

async def word_count():
    return await asyncio.to_thread(_get_word_count_sync)

async def pop_next_word():
    return await asyncio.to_thread(_pop_next_word_sync)
