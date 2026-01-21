import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import google.generativeai as genai

from x_agent_os.agents.twitter_agent import TwitterAgent
from x_agent_os.config import GOOGLE_API_KEY
from x_agent_os.database import DatabaseHandler


def _parse_tweet_date(created_at: Optional[str]) -> Optional[datetime]:
    if not created_at:
        return None
    formats = [
        "%a %b %d %H:%M:%S %z %Y",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(created_at, fmt)
        except ValueError:
            continue
    return None


def _within_days(created_at: Optional[str], days: int, now: datetime) -> bool:
    parsed = _parse_tweet_date(created_at)
    if not parsed:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    return parsed >= now - timedelta(days=days)


def _extract_tweet_id(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    match = re.search(r"/status/(\d+)", url)
    return match.group(1) if match else None


def _engagement_score(tweet: Dict[str, Any]) -> int:
    return int(
        (tweet.get("favorite_count") or 0)
        + (tweet.get("retweet_count") or 0)
        + (tweet.get("reply_count") or 0)
        + (tweet.get("quote_count") or 0)
    )


def _timing_stats(tweets: List[Dict[str, Any]]) -> Dict[str, Any]:
    hours = {str(i): 0 for i in range(24)}
    weekdays = {str(i): 0 for i in range(7)}
    for tweet in tweets:
        parsed = _parse_tweet_date(tweet.get("created_at"))
        if not parsed:
            continue
        parsed = parsed.astimezone(timezone.utc)
        hours[str(parsed.hour)] += 1
        weekdays[str(parsed.weekday())] += 1
    return {"hourly": hours, "weekday": weekdays}


@dataclass
class PersonaRunResult:
    handle: str
    output_json_path: str
    output_md_path: str
    summary: Dict[str, Any]
    cached: bool = False


class CreatorPersonaInspo:
    def __init__(self, db: Optional[DatabaseHandler] = None):
        self.db = db or DatabaseHandler()
        self.twitter = TwitterAgent()
        self.model = None
        if GOOGLE_API_KEY:
            genai.configure(api_key=GOOGLE_API_KEY)
            self.model = genai.GenerativeModel("gemini-3-flash-preview")

    def _output_dir(self, handle: str) -> Path:
        repo_root = Path(__file__).resolve().parents[3]
        base = repo_root / "data" / "creator_persona" / handle.lstrip("@")
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _is_recent_run(self, run: Dict[str, Any], days: int) -> bool:
        if not run:
            return False
        run_at = run.get("run_at")
        if not run_at:
            return False
        parsed = _parse_tweet_date(run_at) or datetime.strptime(run_at, "%Y-%m-%d %H:%M:%S")
        parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed >= datetime.now(timezone.utc) - timedelta(days=days)

    def run(
        self,
        handle: str,
        window_days: int = 30,
        limit: int = 50,
        top_n: int = 7,
        force: bool = False,
    ) -> PersonaRunResult:
        handle = handle.lstrip("@")
        persona_id = self.db.upsert_creator_persona(handle=handle)
        latest_run = self.db.get_latest_creator_persona_run(handle)
        if latest_run and self._is_recent_run(latest_run, window_days) and not force:
            return PersonaRunResult(
                handle=handle,
                output_json_path=latest_run.get("output_json_path", ""),
                output_md_path=latest_run.get("output_md_path", ""),
                summary=latest_run.get("summary_json") or {},
                cached=True,
            )

        if force:
            self.db.clear_creator_persona_data(persona_id)

        now = datetime.now(timezone.utc)
        tweets = self.twitter.search_user_tweets(handle, count=limit, search_type="Latest")
        recent = [tweet for tweet in tweets if _within_days(tweet.get("created_at"), window_days, now)]

        for tweet in recent:
            tweet["tweet_id"] = _extract_tweet_id(tweet.get("url"))
            tweet["engagement_score"] = _engagement_score(tweet)

        ranked = sorted(recent, key=lambda x: x.get("engagement_score", 0), reverse=True)
        top_posts = ranked[:top_n]

        timing = _timing_stats(recent)
        summary = self._summarize(handle, recent, top_posts, timing)

        output_dir = self._output_dir(handle)
        run_stamp = now.strftime("%Y%m%d_%H%M%S")
        run_dir = output_dir / run_stamp
        run_dir.mkdir(parents=True, exist_ok=True)
        json_path = run_dir / "posts.json"
        md_path = run_dir / "summary.md"

        json_payload = {
            "handle": handle,
            "window_days": window_days,
            "captured_at": now.isoformat(),
            "posts": recent,
            "top_posts": top_posts,
            "summary": summary,
            "timing": timing,
        }
        json_path.write_text(json.dumps(json_payload, indent=2), encoding="utf-8")
        md_path.write_text(self._summary_markdown(handle, top_posts, summary, timing), encoding="utf-8")

        db_posts = [
            {
                "tweet_id": tweet.get("tweet_id"),
                "tweet_url": tweet.get("url"),
                "content": tweet.get("snippet"),
                "created_at": tweet.get("created_at"),
                "likes": tweet.get("favorite_count"),
                "replies": tweet.get("reply_count"),
                "retweets": tweet.get("retweet_count"),
                "quotes": tweet.get("quote_count"),
                "impressions": None,
                "bookmarks": None,
                "engagement_score": tweet.get("engagement_score"),
                "raw_json": json.dumps(tweet),
            }
            for tweet in recent
        ]
        if db_posts:
            self.db.insert_creator_persona_posts(persona_id, db_posts)

        self.db.save_creator_persona_run(
            persona_id=persona_id,
            window_days=window_days,
            source="rapidapi_twitter_search",
            output_json_path=str(json_path),
            output_md_path=str(md_path),
            summary_json=summary,
        )

        return PersonaRunResult(
            handle=handle,
            output_json_path=str(json_path),
            output_md_path=str(md_path),
            summary=summary,
            cached=False,
        )

    def _summarize(
        self,
        handle: str,
        posts: List[Dict[str, Any]],
        top_posts: List[Dict[str, Any]],
        timing: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not self.model:
            return {
                "note": "GOOGLE_API_KEY not configured. Summary is a placeholder.",
                "themes": [],
                "structure": [],
                "timing": timing,
            }

        prompt = (
                "You are an expert linguistic and behavioral analyst specializing in extracting the deepest essence of "
                "a creator's communication patterns. You are able to compress writing into its core primitives and reveal "
                "the latent structures that make it persuasive, memorable, and performant. You detect subtext, intent, "
                "psychological levers, pacing techniques, narrative scaffolding, emotional vectors, and rhetorical devices.\n\n"
                
                "Your task is to analyze a creator\’s recent X posts to capture their writing style at the level of:\n"
                "- structural patterns\n"
                "- tone and emotional posture\n"
                "- pacing and rhythm\n"
                "- thematic density\n"
                "- hooks and positioning\n"
                "- implicit beliefs and worldview\n"
                "- performance drivers (why the top posts land)\n"
                "- timing and platform dynamics\n\n"
                
                "Your output should be a JSON object with the following keys:\n"
                "  {\n"
                "    \"themes\": [\"recurring topical and narrative themes\"],\n"
                "    \"structure\": \"how posts are formatted, sequenced, and staged (e.g., setup → tension → reveal)\",\n"
                "    \"tone\": \"voice, affect, stance, and attitude toward the audience\",\n"
                "    \"pacing\": \"how quickly ideas are introduced, escalated, and resolved\",\n"
                "    \"hooks\": [\"hook archetypes and linguistic patterns\"],\n"
                "    \"ctas\": [\"CTA patterns: asks, framing, frequency, positioning\"],\n"
                "    \"timing_notes\": \"observations about posting time, cadence, and engagement correlation\",\n"
                "    \"performance_drivers\": \"why top posts outperform; psychological or rhetorical mechanisms\",\n"
                "    \"essence\": \"a distilled sentence that captures the creator's core writing identity\",\n"
                "    \"emulation_guide\": \"if someone wanted to write like them, what rules would they follow?\"\n"
                "  }\n\n"
                
                "Now analyze the creator below.\n\n"
            f"Handle: @{handle}\n"
            f"Timing stats (UTC): {json.dumps(timing)}\n"
            f"Top posts: {json.dumps(top_posts, indent=2)}\n"
            f"Recent posts sample: {json.dumps(posts[:20], indent=2)}"
        )
        response = self.model.generate_content(prompt)
        if not response.parts:
            return {"note": "Empty summary response", "timing": timing}

        text = response.text.strip()
        try:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1:
                raise ValueError("No JSON found in summary response.")
            return json.loads(text[start : end + 1])
        except Exception:
            return {"note": "Failed to parse summary JSON", "raw": text, "timing": timing}

    def _summary_markdown(
        self,
        handle: str,
        top_posts: List[Dict[str, Any]],
        summary: Dict[str, Any],
        timing: Dict[str, Any],
    ) -> str:
        lines = [
            f"# Creator Persona Inspo — @{handle}",
            "",
            "## Essence",
            json.dumps(summary, indent=2),
            "",
            "## Timing (UTC)",
            json.dumps(timing, indent=2),
            "",
            "## Greatest Hits",
        ]
        for post in top_posts:
            lines.append("")
            lines.append(f"- Engagement: {post.get('engagement_score', 0)}")
            lines.append(f"- URL: {post.get('url')}")
            lines.append(f"- Content: {post.get('snippet')}")
        return "\n".join(lines)
