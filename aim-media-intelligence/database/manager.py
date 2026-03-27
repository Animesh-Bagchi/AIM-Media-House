import sqlite3
import json
import logging
from contextlib import contextmanager
from config import DB_PATH

logger = logging.getLogger(__name__)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS videos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id    TEXT UNIQUE NOT NULL,
                title       TEXT,
                published_at TEXT,
                year        INTEGER,
                view_count  INTEGER DEFAULT 0,
                like_count  INTEGER DEFAULT 0,
                duration    TEXT,
                transcript_raw  TEXT,
                transcript_clean TEXT,
                has_transcript  INTEGER DEFAULT 0,
                is_processed    INTEGER DEFAULT 0,
                is_analyzed     INTEGER DEFAULT 0,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS entities (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id    TEXT NOT NULL,
                year        INTEGER,
                name        TEXT NOT NULL,
                type        TEXT NOT NULL,
                relevance   INTEGER DEFAULT 5,
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
            );

            CREATE TABLE IF NOT EXISTS topics (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id    TEXT NOT NULL,
                year        INTEGER,
                category    TEXT NOT NULL,
                is_primary  INTEGER DEFAULT 0,
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
            );

            CREATE TABLE IF NOT EXISTS sentiments (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id    TEXT UNIQUE NOT NULL,
                year        INTEGER,
                sentiment   TEXT NOT NULL,
                score       REAL,
                reasoning   TEXT,
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
            );

            CREATE TABLE IF NOT EXISTS relationships (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id    TEXT NOT NULL,
                year        INTEGER,
                entity1     TEXT NOT NULL,
                entity2     TEXT NOT NULL,
                context     TEXT,
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
            );

            CREATE TABLE IF NOT EXISTS yearly_summaries (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                year        INTEGER UNIQUE NOT NULL,
                summary     TEXT,
                key_themes  TEXT,
                top_entities TEXT,
                video_count INTEGER,
                generated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
            CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
            CREATE INDEX IF NOT EXISTS idx_entities_year ON entities(year);
            CREATE INDEX IF NOT EXISTS idx_topics_category ON topics(category);
            CREATE INDEX IF NOT EXISTS idx_videos_year ON videos(year);
        """)
    logger.info("Database initialized")


def upsert_video(data: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO videos (video_id, title, published_at, year, view_count, like_count, duration)
            VALUES (:video_id, :title, :published_at, :year, :view_count, :like_count, :duration)
            ON CONFLICT(video_id) DO UPDATE SET
                title=excluded.title,
                view_count=excluded.view_count,
                like_count=excluded.like_count
        """, data)


def store_transcript(video_id: str, raw: str, clean: str):
    with get_conn() as conn:
        conn.execute("""
            UPDATE videos
            SET transcript_raw=?, transcript_clean=?, has_transcript=1, is_processed=1
            WHERE video_id=?
        """, (raw, clean, video_id))


def mark_no_transcript(video_id: str):
    with get_conn() as conn:
        conn.execute("UPDATE videos SET has_transcript=0, is_processed=1 WHERE video_id=?", (video_id,))


def get_unprocessed_videos(limit=500):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT video_id, title FROM videos WHERE is_processed=0 LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_unanalyzed_videos(limit=500):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT video_id, title, published_at, year, view_count, transcript_clean
            FROM videos
            WHERE is_analyzed=0 AND has_transcript=1 AND transcript_clean IS NOT NULL
            ORDER BY view_count DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def store_analysis(video_id: str, year: int, entities: list, topics: list, sentiment: dict, relationships: list):
    with get_conn() as conn:
        # entities
        for e in entities:
            conn.execute(
                "INSERT INTO entities (video_id, year, name, type, relevance) VALUES (?,?,?,?,?)",
                (video_id, year, e.get("name", ""), e.get("type", "unknown"), e.get("relevance", 5))
            )
        # topics
        for i, t in enumerate(topics):
            conn.execute(
                "INSERT INTO topics (video_id, year, category, is_primary) VALUES (?,?,?,?)",
                (video_id, year, t, 1 if i == 0 else 0)
            )
        # sentiment
        conn.execute("""
            INSERT OR REPLACE INTO sentiments (video_id, year, sentiment, score, reasoning)
            VALUES (?,?,?,?,?)
        """, (video_id, year, sentiment.get("overall", "neutral"),
              sentiment.get("score", 0.5), sentiment.get("reasoning", "")))
        # relationships
        for r in relationships:
            conn.execute(
                "INSERT INTO relationships (video_id, year, entity1, entity2, context) VALUES (?,?,?,?,?)",
                (video_id, year, r.get("entity1", ""), r.get("entity2", ""), r.get("context", ""))
            )
        conn.execute("UPDATE videos SET is_analyzed=1 WHERE video_id=?", (video_id,))


def store_yearly_summary(year: int, summary: str, key_themes: list, top_entities: list, video_count: int):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO yearly_summaries (year, summary, key_themes, top_entities, video_count)
            VALUES (?,?,?,?,?)
        """, (year, summary, json.dumps(key_themes), json.dumps(top_entities), video_count))


def get_stats():
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        with_transcript = conn.execute("SELECT COUNT(*) FROM videos WHERE has_transcript=1").fetchone()[0]
        analyzed = conn.execute("SELECT COUNT(*) FROM videos WHERE is_analyzed=1").fetchone()[0]
        years = conn.execute("SELECT MIN(year), MAX(year) FROM videos WHERE year IS NOT NULL").fetchone()
    return {"total": total, "with_transcript": with_transcript, "analyzed": analyzed,
            "year_range": (years[0], years[1]) if years[0] else (None, None)}


def get_top_entities(entity_type=None, limit=30, year=None):
    with get_conn() as conn:
        q = "SELECT name, type, COUNT(*) as count FROM entities WHERE 1=1"
        params = []
        if entity_type:
            q += " AND type=?"
            params.append(entity_type)
        if year:
            q += " AND year=?"
            params.append(year)
        q += " GROUP BY name, type ORDER BY count DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def get_entity_trends(entity_name: str):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT year, COUNT(*) as count
            FROM entities WHERE name=? AND year IS NOT NULL
            GROUP BY year ORDER BY year
        """, (entity_name,)).fetchall()
    return [dict(r) for r in rows]


def get_topic_distribution(year=None):
    with get_conn() as conn:
        q = "SELECT category, COUNT(*) as count FROM topics WHERE 1=1"
        params = []
        if year:
            q += " AND year=?"
            params.append(year)
        q += " GROUP BY category ORDER BY count DESC"
        rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def get_yearly_entity_trends():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT year, name, type, COUNT(*) as count
            FROM entities
            WHERE year IS NOT NULL
            GROUP BY year, name, type
            ORDER BY year, count DESC
        """).fetchall()
    return [dict(r) for r in rows]


def get_sentiment_distribution(year=None):
    with get_conn() as conn:
        q = "SELECT sentiment, COUNT(*) as count, AVG(score) as avg_score FROM sentiments WHERE 1=1"
        params = []
        if year:
            q += " AND year=?"
            params.append(year)
        q += " GROUP BY sentiment"
        rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def get_yearly_summaries():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM yearly_summaries ORDER BY year"
        ).fetchall()
    return [dict(r) for r in rows]


def get_relationships(limit=200):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT entity1, entity2, COUNT(*) as weight, GROUP_CONCAT(DISTINCT context) as contexts
            FROM relationships
            WHERE entity1 != '' AND entity2 != ''
            GROUP BY entity1, entity2
            ORDER BY weight DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_yearly_video_counts():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT year, COUNT(*) as count, SUM(view_count) as total_views
            FROM videos WHERE year IS NOT NULL
            GROUP BY year ORDER BY year
        """).fetchall()
    return [dict(r) for r in rows]
