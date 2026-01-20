import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _default_db_path() -> str:
    env_path = os.getenv("X_AGENT_OS_DB_PATH")
    if env_path:
        return env_path
    repo_root = Path(__file__).resolve().parents[2]
    data_dir = repo_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir / "x_agent_os.db")


class DatabaseHandler:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _default_db_path()
        self.init_database()
        self.migrate_database()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def migrate_database(self):
        """Apply targeted schema migrations for legacy tables."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(twitter_results)")
            columns = [column[1] for column in cursor.fetchall()]
            if "tweet_created_at" not in columns:
                cursor.execute(
                    """
                    ALTER TABLE twitter_results
                    ADD COLUMN tweet_created_at TEXT
                    """
                )
            conn.commit()

    def init_database(self):
        """Initialize the database with legacy + X Agent OS tables."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # --- Legacy tables (keep intact) ---
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    topic TEXT,
                    app_name TEXT,
                    app_description TEXT
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS search_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    url TEXT,
                    snippet TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    raw_response TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS twitter_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    url TEXT,
                    snippet TEXT,
                    screen_name TEXT,
                    followers_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    tweet_created_at TEXT,
                    favorite_count INTEGER DEFAULT 0,
                    quote_count INTEGER DEFAULT 0,
                    reply_count INTEGER DEFAULT 0,
                    retweet_count INTEGER DEFAULT 0,
                    raw_response TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS reviewer_outputs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    distilled_topics TEXT,
                    talking_points TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    raw_response TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS editor_outputs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    topic TEXT,
                    linkedin_post TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    raw_response TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS content_fingerprints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_type TEXT NOT NULL,
                    primary_identifier TEXT NOT NULL,
                    url TEXT,
                    content_hash TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processing_status TEXT DEFAULT 'new',
                    platform_metadata TEXT,
                    UNIQUE(content_type, primary_identifier)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS processing_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_date DATE NOT NULL,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    status TEXT DEFAULT 'running',
                    new_search_results INTEGER DEFAULT 0,
                    new_tweets INTEGER DEFAULT 0,
                    duplicates_skipped INTEGER DEFAULT 0,
                    content_generated INTEGER DEFAULT 0,
                    session_id INTEGER,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
                """
            )

            # --- X Agent OS tables ---
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS skills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slug TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    priority REAL DEFAULT 0.5,
                    config_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    skill_slug TEXT,
                    platform TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    source TEXT NOT NULL,
                    draft_content TEXT NOT NULL,
                    published_content TEXT,
                    typefully_draft_id TEXT,
                    x_tweet_id TEXT,
                    x_thread_root_id TEXT,
                    planned_for TIMESTAMP,
                    published_at TIMESTAMP,
                    metadata_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    skill_slug TEXT,
                    x_tweet_url TEXT NOT NULL,
                    x_tweet_id TEXT,
                    author_handle TEXT,
                    author_followers INTEGER,
                    snippet TEXT,
                    reason TEXT,
                    suggested_reply TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_briefs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE NOT NULL,
                    content_md TEXT NOT NULL,
                    summary_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS metrics_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id INTEGER NOT NULL,
                    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    impressions INTEGER,
                    likes INTEGER,
                    replies INTEGER,
                    retweets INTEGER,
                    bookmarks INTEGER,
                    profile_visits INTEGER,
                    link_clicks INTEGER,
                    raw_json TEXT,
                    FOREIGN KEY (post_id) REFERENCES posts (id)
                )
                """
            )

            conn.commit()

    # --- Session methods ---
    def create_session(
        self,
        session_name: str,
        topic: Optional[str] = None,
        app_name: Optional[str] = None,
        app_description: Optional[str] = None,
    ) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sessions (session_name, topic, app_name, app_description)
                VALUES (?, ?, ?, ?)
                """,
                (session_name, topic, app_name, app_description),
            )
            conn.commit()
            return cursor.lastrowid

    def get_sessions(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, session_name, created_at, topic, app_name, app_description
                FROM sessions
                ORDER BY created_at DESC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_latest_session_id(self) -> Optional[int]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM sessions ORDER BY created_at DESC LIMIT 1")
            result = cursor.fetchone()
            return result[0] if result else None

    # --- Search results ---
    def save_search_results(self, session_id: int, results: List[Dict[str, Any]], raw_response: Optional[str] = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for result in results:
                cursor.execute(
                    """
                    INSERT INTO search_results (session_id, url, snippet, raw_response)
                    VALUES (?, ?, ?, ?)
                    """,
                    (session_id, result.get("url"), result.get("snippet"), raw_response),
                )
            conn.commit()

    def get_search_results(self, session_id: Optional[int] = None) -> List[Dict[str, Any]]:
        if session_id is None:
            session_id = self.get_latest_session_id()
        if session_id is None:
            return []
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT url, snippet, created_at, raw_response
                FROM search_results
                WHERE session_id = ?
                ORDER BY created_at
                """,
                (session_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def has_search_results(self, session_id: Optional[int] = None) -> bool:
        if session_id is None:
            session_id = self.get_latest_session_id()
        if session_id is None:
            return False
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM search_results WHERE session_id = ?", (session_id,))
            return cursor.fetchone()[0] > 0

    # --- Twitter results ---
    def save_twitter_results(self, session_id: int, results: List[Dict[str, Any]], raw_response: Optional[str] = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for result in results:
                cursor.execute(
                    """
                    INSERT INTO twitter_results
                    (session_id, url, snippet, screen_name, followers_count, tweet_created_at,
                     favorite_count, quote_count, reply_count, retweet_count, raw_response)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        result.get("url"),
                        result.get("snippet"),
                        result.get("screen_name"),
                        result.get("followers_count", 0),
                        result.get("created_at"),
                        result.get("favorite_count", 0),
                        result.get("quote_count", 0),
                        result.get("reply_count", 0),
                        result.get("retweet_count", 0),
                        raw_response,
                    ),
                )
            conn.commit()

    def get_twitter_results(self, session_id: Optional[int] = None) -> List[Dict[str, Any]]:
        if session_id is None:
            session_id = self.get_latest_session_id()
        if session_id is None:
            return []
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT url, snippet, screen_name, followers_count,
                       COALESCE(tweet_created_at, created_at) as created_at,
                       favorite_count, quote_count, reply_count, retweet_count, raw_response
                FROM twitter_results
                WHERE session_id = ?
                ORDER BY COALESCE(tweet_created_at, created_at)
                """,
                (session_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def has_twitter_results(self, session_id: Optional[int] = None) -> bool:
        if session_id is None:
            session_id = self.get_latest_session_id()
        if session_id is None:
            return False
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM twitter_results WHERE session_id = ?", (session_id,))
            return cursor.fetchone()[0] > 0

    # --- Reviewer outputs ---
    def save_reviewer_output(
        self,
        session_id: int,
        distilled_topics: List[str],
        talking_points: List[str],
        raw_response: Optional[str] = None,
    ):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO reviewer_outputs (session_id, distilled_topics, talking_points, raw_response)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, json.dumps(distilled_topics), json.dumps(talking_points), raw_response),
            )
            conn.commit()

    def get_reviewer_output(self, session_id: Optional[int] = None) -> Dict[str, Any]:
        if session_id is None:
            session_id = self.get_latest_session_id()
        if session_id is None:
            return {"distilled_topics": [], "talking_points": []}
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT distilled_topics, talking_points, created_at, raw_response
                FROM reviewer_outputs
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (session_id,),
            )
            result = cursor.fetchone()
            if result:
                return {
                    "distilled_topics": json.loads(result["distilled_topics"]),
                    "talking_points": json.loads(result["talking_points"]),
                    "created_at": result["created_at"],
                    "raw_response": result["raw_response"],
                }
            return {"distilled_topics": [], "talking_points": []}

    def has_reviewer_output(self, session_id: Optional[int] = None) -> bool:
        if session_id is None:
            session_id = self.get_latest_session_id()
        if session_id is None:
            return False
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM reviewer_outputs WHERE session_id = ?", (session_id,))
            return cursor.fetchone()[0] > 0

    # --- Editor outputs ---
    def save_editor_outputs(
        self, session_id: int, posts: List[Dict[str, Any]], raw_responses: Optional[List[str]] = None
    ):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for i, post in enumerate(posts):
                raw_response = raw_responses[i] if raw_responses and i < len(raw_responses) else None
                cursor.execute(
                    """
                    INSERT INTO editor_outputs (session_id, topic, linkedin_post, raw_response)
                    VALUES (?, ?, ?, ?)
                    """,
                    (session_id, post.get("topic"), post.get("linkedin_post"), raw_response),
                )
            conn.commit()

    def get_editor_outputs(self, session_id: Optional[int] = None) -> List[Dict[str, Any]]:
        if session_id is None:
            session_id = self.get_latest_session_id()
        if session_id is None:
            return []
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT topic, linkedin_post, created_at, raw_response
                FROM editor_outputs
                WHERE session_id = ?
                ORDER BY created_at
                """,
                (session_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def has_editor_outputs(self, session_id: Optional[int] = None) -> bool:
        if session_id is None:
            session_id = self.get_latest_session_id()
        if session_id is None:
            return False
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM editor_outputs WHERE session_id = ?", (session_id,))
            return cursor.fetchone()[0] > 0

    # --- Content fingerprinting ---
    def check_content_fingerprint(self, content_type: str, primary_identifier: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM content_fingerprints
                WHERE content_type = ? AND primary_identifier = ?
                """,
                (content_type, primary_identifier),
            )
            result = cursor.fetchone()
            return dict(result) if result else None

    def save_content_fingerprint(
        self,
        content_type: str,
        primary_identifier: str,
        url: str,
        content_hash: str,
        platform: str,
        platform_metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            metadata_json = json.dumps(platform_metadata) if platform_metadata else None
            cursor.execute(
                """
                INSERT INTO content_fingerprints
                (content_type, primary_identifier, url, content_hash, platform, platform_metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (content_type, primary_identifier, url, content_hash, platform, metadata_json),
            )
            conn.commit()
            return cursor.lastrowid

    def update_fingerprint_status(self, fingerprint_id: int, status: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE content_fingerprints
                SET processing_status = ?, last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, fingerprint_id),
            )
            conn.commit()

    # --- Processing runs ---
    def create_processing_run(self, run_date: str, session_id: int) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO processing_runs (run_date, session_id)
                VALUES (?, ?)
                """,
                (run_date, session_id),
            )
            conn.commit()
            return cursor.lastrowid

    def update_processing_run(self, run_id: int, **kwargs):
        set_clauses = []
        values = []
        for key, value in kwargs.items():
            if key in [
                "new_search_results",
                "new_tweets",
                "duplicates_skipped",
                "content_generated",
                "status",
            ]:
                set_clauses.append(f"{key} = ?")
                values.append(value)
        if "status" in kwargs and kwargs["status"] == "completed":
            set_clauses.append("completed_at = CURRENT_TIMESTAMP")
        if set_clauses:
            values.append(run_id)
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    UPDATE processing_runs
                    SET {', '.join(set_clauses)}
                    WHERE id = ?
                    """,
                    values,
                )
                conn.commit()

    def get_latest_processing_run(self) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM processing_runs
                ORDER BY started_at DESC
                LIMIT 1
                """
            )
            result = cursor.fetchone()
            return dict(result) if result else None

    # --- Skills ---
    def upsert_skill(
        self,
        slug: str,
        name: str,
        skill_type: str,
        status: str,
        priority: float,
        config_json: Dict[str, Any],
    ):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO skills (slug, name, type, status, priority, config_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    name = excluded.name,
                    type = excluded.type,
                    status = excluded.status,
                    priority = excluded.priority,
                    config_json = excluded.config_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (slug, name, skill_type, status, priority, json.dumps(config_json)),
            )
            conn.commit()

    def list_skills(self, include_inactive: bool = True) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if include_inactive:
                cursor.execute(
                    """
                    SELECT id, slug, name, type, status, priority, config_json, created_at, updated_at
                    FROM skills
                    ORDER BY priority DESC, name ASC
                    """
                )
            else:
                cursor.execute(
                    """
                    SELECT id, slug, name, type, status, priority, config_json, created_at, updated_at
                    FROM skills
                    WHERE status = 'active'
                    ORDER BY priority DESC, name ASC
                    """
                )
            rows = [dict(row) for row in cursor.fetchall()]
            for row in rows:
                row["config_json"] = json.loads(row["config_json"])
            return rows

    def get_active_skills(self) -> List[Dict[str, Any]]:
        return self.list_skills(include_inactive=False)

    def update_skill_config(self, slug: str, config_json: Dict[str, Any]):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE skills
                SET config_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE slug = ?
                """,
                (json.dumps(config_json), slug),
            )
            conn.commit()

    # --- Posts ---
    def create_post(
        self,
        session_id: Optional[int],
        skill_slug: Optional[str],
        platform: str,
        kind: str,
        source: str,
        draft_content: str,
        planned_for: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO posts
                (session_id, skill_slug, platform, kind, source, draft_content, planned_for, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    skill_slug,
                    platform,
                    kind,
                    source,
                    draft_content,
                    planned_for,
                    json.dumps(metadata_json) if metadata_json else None,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def list_pending_posts_for_today(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT *
                FROM posts
                WHERE published_at IS NULL
                ORDER BY created_at DESC
                """
            )
            rows = [dict(row) for row in cursor.fetchall()]
            for row in rows:
                row["metadata_json"] = json.loads(row["metadata_json"]) if row.get("metadata_json") else None
            return rows

    def update_post_content(self, post_id: int, draft_content: Optional[str] = None):
        if draft_content is None:
            return
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE posts
                SET draft_content = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (draft_content, post_id),
            )
            conn.commit()

    def mark_post_approved(self, post_id: int, approved_by: str = "dashboard"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT metadata_json FROM posts WHERE id = ?", (post_id,))
            row = cursor.fetchone()
            metadata = json.loads(row["metadata_json"]) if row and row["metadata_json"] else {}
            metadata["approved"] = True
            metadata["approved_by"] = approved_by
            metadata["approved_at"] = datetime.utcnow().isoformat()
            cursor.execute(
                """
                UPDATE posts
                SET metadata_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(metadata), post_id),
            )
            conn.commit()

    def update_post_typefully_id(self, post_id: int, typefully_draft_id: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE posts
                SET typefully_draft_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (typefully_draft_id, post_id),
            )
            conn.commit()

    def update_post_metrics(self, post_id: int, metadata_json: Dict[str, Any]):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE posts
                SET metadata_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(metadata_json), post_id),
            )
            conn.commit()

    # --- Conversations ---
    def add_conversation(
        self,
        session_id: Optional[int],
        skill_slug: Optional[str],
        x_tweet_url: str,
        snippet: Optional[str] = None,
        reason: Optional[str] = None,
        suggested_reply: Optional[str] = None,
        author_handle: Optional[str] = None,
        author_followers: Optional[int] = None,
        x_tweet_id: Optional[str] = None,
    ) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO conversations
                (session_id, skill_slug, x_tweet_url, x_tweet_id, author_handle, author_followers,
                 snippet, reason, suggested_reply)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    skill_slug,
                    x_tweet_url,
                    x_tweet_id,
                    author_handle,
                    author_followers,
                    snippet,
                    reason,
                    suggested_reply,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def list_pending_conversations(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT *
                FROM conversations
                WHERE status = 'pending'
                ORDER BY created_at DESC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def mark_conversation_status(self, conversation_id: int, status: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE conversations
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, conversation_id),
            )
            conn.commit()

    # --- Daily briefs ---
    def save_daily_brief(self, date: str, content_md: str, summary_json: Optional[Dict[str, Any]] = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO daily_briefs (date, content_md, summary_json)
                VALUES (?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    content_md = excluded.content_md,
                    summary_json = excluded.summary_json
                """,
                (date, content_md, json.dumps(summary_json) if summary_json else None),
            )
            conn.commit()

    def get_daily_brief(self, date: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM daily_briefs
                WHERE date = ?
                """,
                (date,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            result = dict(row)
            result["summary_json"] = (
                json.loads(result["summary_json"]) if result.get("summary_json") else None
            )
            return result

    # --- Metrics ---
    def insert_metrics_snapshot(self, post_id: int, metrics_json: Dict[str, Any]):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO metrics_snapshots
                (post_id, impressions, likes, replies, retweets, bookmarks,
                 profile_visits, link_clicks, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    post_id,
                    metrics_json.get("impressions"),
                    metrics_json.get("likes"),
                    metrics_json.get("replies"),
                    metrics_json.get("retweets"),
                    metrics_json.get("bookmarks"),
                    metrics_json.get("profile_visits"),
                    metrics_json.get("link_clicks"),
                    json.dumps(metrics_json),
                ),
            )
            conn.commit()

    def get_metrics_for_post(self, post_id: int) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM metrics_snapshots
                WHERE post_id = ?
                ORDER BY captured_at DESC
                """,
                (post_id,),
            )
            rows = [dict(row) for row in cursor.fetchall()]
            for row in rows:
                row["raw_json"] = json.loads(row["raw_json"]) if row.get("raw_json") else None
            return rows

    def list_recent_published_posts(self, days: int = 14) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT *
                FROM posts
                WHERE published_at IS NOT NULL
                AND published_at >= datetime('now', ?)
                ORDER BY published_at DESC
                """,
                (f"-{days} days",),
            )
            return [dict(row) for row in cursor.fetchall()]
