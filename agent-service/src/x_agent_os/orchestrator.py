import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from x_agent_os.agents.editor_agent import EditorAgent
from x_agent_os.agents.reviewer_agent import ReviewerAgent
from x_agent_os.agents.search_agent import SearchAgent
from x_agent_os.agents.twitter_agent import TwitterAgent
from x_agent_os.content_fingerprinting import IncrementalProcessingManager
from x_agent_os.daily_brief import DailyBriefGenerator
from x_agent_os.database import DatabaseHandler
from x_agent_os.metrics import MetricsCollector
from x_agent_os.skills import SkillManager


def _pick_query(skill_config: Dict[str, Any]) -> str:
    queries = skill_config.get("research_queries") or []
    if queries:
        return queries[0]
    return skill_config.get("description", "research topics")


def _summarize_feature_notes(skill_config: Dict[str, Any]) -> str:
    return (
        "Skill configuration:\n"
        + "\n".join(
            [
                f"- {key}: {value}"
                for key, value in skill_config.items()
                if key not in {"name", "slug", "type", "status", "priority"}
            ]
        )
    )


def _format_internal_skill(skill: Dict[str, Any]) -> str:
    config = skill["config_json"]
    lines = [f"Internal skill: {skill['slug']} ({skill['name']})"]
    for key in [
        "description",
        "values",
        "voice_notes",
        "lexicon",
        "avoid",
        "pillars",
        "style_constraints",
        "grounding_procedure",
        "brand_manifesto_md",
    ]:
        if key in config:
            lines.append(f"{key}: {config[key]}")
    return "\n".join(lines)


def _internal_skill_context(skills: List[Dict[str, Any]]) -> str:
    if not skills:
        return ""
    chunks = ["Internal skills context:"]
    for skill in skills:
        chunks.append(_format_internal_skill(skill))
    return "\n\n".join(chunks)


def _recency_query(query: str, days: int) -> str:
    return f"{query} (last {days} days)"


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


def _is_within_days(created_at: Optional[str], days: int, now: datetime) -> bool:
    parsed = _parse_tweet_date(created_at)
    if not parsed:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    now_utc = now.astimezone(timezone.utc)
    return parsed >= now_utc - timedelta(days=days)


def _clean_snippet(snippet: str) -> str:
    cleaned = re.sub(r"https?://\S+", "", snippet or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _build_suggested_reply(snippet: str, skill_name: str, reply_style: Optional[str]) -> str:
    cleaned = _clean_snippet(snippet)
    anchor = cleaned.split(".")[0].strip() if cleaned else ""
    opener = f"Interesting take on {anchor.lower()}." if anchor else "Appreciate you sharing this."
    if reply_style and reply_style[-1] in {".", "?", "!"}:
        closer = reply_style
    else:
        closer = "Curious how you decide what belongs in the core workflow vs what gets split out?"
    return f"{opener} {closer}"


def _persona_context(db: DatabaseHandler, limit: int = 2, posts_limit: int = 3) -> str:
    personas = db.list_creator_personas(active_only=True)
    if not personas:
        return ""
    chunks: List[str] = ["Creator persona inspo (active):"]
    for persona in personas[:limit]:
        handle = persona.get("handle")
        run = db.get_latest_creator_persona_run(handle)
        posts = db.list_creator_persona_posts(persona["id"], limit=posts_limit)
        chunks.append(f"- @{handle}")
        if run and run.get("summary_json"):
            chunks.append(f"  summary: {run['summary_json']}")
        if posts:
            for post in posts:
                chunks.append(f"  hit: {post.get('content')}")
    return "\n".join(chunks)


def run_daily_pipeline(date: Optional[str] = None) -> Dict[str, Any]:
    run_date = date or datetime.utcnow().strftime("%Y-%m-%d")
    db = DatabaseHandler()
    skill_manager = SkillManager(db)

    skill_manager.seed_missing_skills()
    active_skills = skill_manager.get_active_skills()
    if not active_skills:
        skill_manager.seed_database()
        active_skills = skill_manager.get_active_skills()

    search_agent = SearchAgent()
    twitter_agent = TwitterAgent()
    reviewer_agent = ReviewerAgent()
    editor_agent = EditorAgent()
    processor = IncrementalProcessingManager(db)

    pipeline_summary = {
        "date": run_date,
        "skills_processed": 0,
        "posts_created": 0,
        "conversations_created": 0,
    }

    recency_days = 30
    now = datetime.now(timezone.utc)

    internal_skills = [skill for skill in active_skills if skill.get("type") == "internal"]
    generation_skills = [skill for skill in active_skills if skill.get("type") != "internal"]
    internal_context = _internal_skill_context(internal_skills)
    persona_context = _persona_context(db)

    for skill in generation_skills:
        skill_config = skill["config_json"]
        skill_slug = skill["slug"]
        skill_name = skill["name"]
        query = _recency_query(_pick_query(skill_config), recency_days)

        session_name = f"{run_date} - {skill_slug} - daily run"
        session_id = db.create_session(
            session_name=session_name,
            topic=query,
            app_name=skill_name,
            app_description=skill_config.get("description"),
        )

        processing_run_id = db.create_processing_run(run_date, session_id)

        search_result = search_agent.search_incremental(query, session_id)
        twitter_result = twitter_agent.search_tweets_incremental(query, session_id=session_id)

        new_search = search_result.get("new_results", [])
        new_tweets = twitter_result.get("new_results", [])
        recent_tweets = [
            tweet
            for tweet in new_tweets
            if _is_within_days(tweet.get("created_at"), recency_days, now)
        ]
        duplicate_count = search_result.get("duplicate_count", 0) + twitter_result.get("duplicate_count", 0)
        new_fingerprint_ids: List[int] = []
        new_fingerprint_ids.extend(search_result.get("new_fingerprint_ids", []))
        new_fingerprint_ids.extend(twitter_result.get("new_fingerprint_ids", []))

        combined = new_search + recent_tweets
        if not combined:
            db.update_processing_run(
                processing_run_id,
                new_search_results=len(new_search),
                new_tweets=len(recent_tweets),
                duplicates_skipped=duplicate_count,
                content_generated=0,
                status="completed_no_new_content",
            )
            continue

        reviewer_output = reviewer_agent.review_and_distill(
            combined,
            skill_name,
            skill_config.get("description", ""),
            "\n\n".join(
                filter(
                    None,
                    [
                        _summarize_feature_notes(skill_config),
                        persona_context,
                        internal_context,
                    ],
                )
            ),
            session_id,
        )

        editor_outputs = editor_agent.craft_posts(
            reviewer_output,
            skill_name,
            skill_config.get("description", ""),
            "\n\n".join(
                filter(
                    None,
                    [
                        _summarize_feature_notes(skill_config),
                        persona_context,
                        internal_context,
                    ],
                )
            ),
            session_id,
        )

        created_posts = 0
        for post in editor_outputs:
            if not post.get("linkedin_post"):
                continue
            db.create_post(
                session_id=session_id,
                skill_slug=skill_slug,
                platform="x",
                kind="short_post",
                source="agent",
                draft_content=post["linkedin_post"],
                metadata_json={"topic": post.get("topic")},
            )
            created_posts += 1

        created_conversations = 0
        for tweet in recent_tweets[:5]:
            snippet = tweet.get("snippet", "")
            suggested_reply = _build_suggested_reply(
                snippet=snippet,
                skill_name=skill_name,
                reply_style=skill_config.get("reply_style"),
            )
            db.add_conversation(
                session_id=session_id,
                skill_slug=skill_slug,
                x_tweet_url=tweet.get("url") or "",
                x_tweet_id=None,
                author_handle=tweet.get("screen_name"),
                author_followers=tweet.get("followers_count"),
                snippet=snippet,
                reason="High-signal tweet from skill query",
                suggested_reply=suggested_reply,
            )
            created_conversations += 1

        if new_fingerprint_ids:
            processor.mark_content_as_processed(new_fingerprint_ids)

        db.update_processing_run(
            processing_run_id,
            new_search_results=len(new_search),
            new_tweets=len(recent_tweets),
            duplicates_skipped=duplicate_count,
            content_generated=created_posts,
            status="completed",
        )

        pipeline_summary["skills_processed"] += 1
        pipeline_summary["posts_created"] += created_posts
        pipeline_summary["conversations_created"] += created_conversations

    DailyBriefGenerator(db).generate_and_save(run_date)
    return pipeline_summary


def run_metrics_update(days: int = 14) -> Dict[str, Any]:
    collector = MetricsCollector(DatabaseHandler())
    written = collector.run_metrics_update(days=days)
    return {"snapshots_written": written, "days": days}
