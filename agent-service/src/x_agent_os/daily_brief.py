import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from x_agent_os.database import DatabaseHandler


class DailyBriefGenerator:
    def __init__(self, db: DatabaseHandler | None = None):
        self.db = db or DatabaseHandler()

    def _aggregate_yesterday_metrics(self, date: str) -> Dict[str, Any]:
        target = datetime.strptime(date, "%Y-%m-%d").date() - timedelta(days=1)
        start = f"{target} 00:00:00"
        end = f"{target} 23:59:59"
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    SUM(impressions) as impressions,
                    SUM(likes) as likes,
                    SUM(replies) as replies,
                    SUM(retweets) as retweets,
                    SUM(bookmarks) as bookmarks,
                    SUM(profile_visits) as profile_visits,
                    SUM(link_clicks) as link_clicks,
                    COUNT(*) as snapshots
                FROM metrics_snapshots
                WHERE captured_at BETWEEN ? AND ?
                """,
                (start, end),
            )
            row = cursor.fetchone()
            if not row:
                return {}
            return {key: row[key] for key in row.keys()}

    def generate_brief(self, date: str) -> Dict[str, Any]:
        pending_posts = self.db.list_pending_posts_for_today()
        pending_conversations = self.db.list_pending_conversations()
        metrics_summary = self._aggregate_yesterday_metrics(date)

        summary = {
            "date": date,
            "pending_posts": len(pending_posts),
            "pending_conversations": len(pending_conversations),
            "metrics_summary": metrics_summary,
        }

        lines: List[str] = []
        lines.append(f"# Daily Brief — {date}")
        lines.append("")
        lines.append("## What happened yesterday")
        if metrics_summary.get("snapshots"):
            lines.append(
                f"- {metrics_summary.get('snapshots', 0)} metric snapshots captured"
            )
            lines.append(
                f"- Impressions: {metrics_summary.get('impressions', 0) or 0}"
            )
            lines.append(f"- Likes: {metrics_summary.get('likes', 0) or 0}")
            lines.append(f"- Replies: {metrics_summary.get('replies', 0) or 0}")
            lines.append(f"- Retweets: {metrics_summary.get('retweets', 0) or 0}")
        else:
            lines.append("- No metrics captured yet (metrics pipeline pending)")

        lines.append("")
        lines.append("## Publish these")
        if pending_posts:
            for post in pending_posts:
                preview = post["draft_content"][:180].replace("\n", " ")
                lines.append(
                    f"- Post #{post['id']} ({post.get('skill_slug') or 'unspecified'}) "
                    f"[{post.get('kind')}] — {preview}..."
                )
        else:
            lines.append("- No pending posts")

        lines.append("")
        lines.append("## Join these conversations")
        if pending_conversations:
            for convo in pending_conversations:
                snippet = (convo.get("snippet") or "").replace("\n", " ")
                lines.append(
                    f"- Convo #{convo['id']} ({convo.get('skill_slug') or 'unspecified'}) — "
                    f"{snippet[:160]}..."
                )
                if convo.get("x_tweet_url"):
                    lines.append(f"  - {convo['x_tweet_url']}")
        else:
            lines.append("- No pending conversations")

        lines.append("")
        lines.append("## Skill proposals / updates")
        lines.append("- No new skill proposals yet (stub)")

        return {"content_md": "\n".join(lines), "summary_json": summary}

    def generate_and_save(self, date: str):
        brief = self.generate_brief(date)
        self.db.save_daily_brief(date, brief["content_md"], brief["summary_json"])
        return brief
