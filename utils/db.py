# utils/db.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import asyncio
from typing import List, Optional, Dict

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise SystemExit("DATABASE_URL not set in environment")

def get_conn():
    return psycopg2.connect(DATABASE_URL)

# --- synchronous helpers ---

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

def _get_words_sync(limit: int = 200) -> List[Dict]:
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
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

def _pop_next_word_sync() -> Optional[Dict]:
    """
    Transactional pop using SKIP LOCKED to avoid race conditions.
    Returns a dict or None.
    """
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Start a transaction
        cur.execute("BEGIN;")
        cur.execute("""
            SELECT id, word, language, added_by, added_at
            FROM words
            ORDER BY id ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1;
        """)
        row = cur.fetchone()
        if row:
            cur.execute("DELETE FROM words WHERE id = %s;", (row["id"],))
        conn.commit()
        return row
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

# --- async wrappers ---

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
