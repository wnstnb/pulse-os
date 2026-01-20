from typing import Any, Dict, Optional

from agent_service.database import DatabaseHandler


class MetricsCollector:
    def __init__(self, db: DatabaseHandler | None = None):
        self.db = db or DatabaseHandler()

    def fetch_metrics_for_post(self, post: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Placeholder for metrics retrieval. Extend with Typefully/X API integration.
        """
        if not post.get("x_tweet_id") and not post.get("typefully_draft_id"):
            return None
        return None

    def run_metrics_update(self, days: int = 14) -> int:
        posts = self.db.list_recent_published_posts(days=days)
        snapshots_written = 0
        for post in posts:
            metrics = self.fetch_metrics_for_post(post)
            if metrics:
                self.db.insert_metrics_snapshot(post["id"], metrics)
                snapshots_written += 1
        return snapshots_written
