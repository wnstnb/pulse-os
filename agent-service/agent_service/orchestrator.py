from datetime import datetime
from typing import Any, Dict, List, Optional

from agent_service.agents.editor_agent import EditorAgent
from agent_service.agents.reviewer_agent import ReviewerAgent
from agent_service.agents.search_agent import SearchAgent
from agent_service.agents.twitter_agent import TwitterAgent
from agent_service.content_fingerprinting import IncrementalProcessingManager
from agent_service.daily_brief import DailyBriefGenerator
from agent_service.database import DatabaseHandler
from agent_service.metrics import MetricsCollector
from agent_service.skills import SkillManager


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


def run_daily_pipeline(date: Optional[str] = None) -> Dict[str, Any]:
    run_date = date or datetime.utcnow().strftime("%Y-%m-%d")
    db = DatabaseHandler()
    skill_manager = SkillManager(db)

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

    for skill in active_skills:
        skill_config = skill["config_json"]
        skill_slug = skill["slug"]
        skill_name = skill["name"]
        query = _pick_query(skill_config)

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
        duplicate_count = search_result.get("duplicate_count", 0) + twitter_result.get("duplicate_count", 0)
        new_fingerprint_ids: List[int] = []
        new_fingerprint_ids.extend(search_result.get("new_fingerprint_ids", []))
        new_fingerprint_ids.extend(twitter_result.get("new_fingerprint_ids", []))

        combined = new_search + new_tweets
        if not combined:
            db.update_processing_run(
                processing_run_id,
                new_search_results=len(new_search),
                new_tweets=len(new_tweets),
                duplicates_skipped=duplicate_count,
                content_generated=0,
                status="completed_no_new_content",
            )
            continue

        reviewer_output = reviewer_agent.review_and_distill(
            combined,
            skill_name,
            skill_config.get("description", ""),
            _summarize_feature_notes(skill_config),
            session_id,
        )

        editor_outputs = editor_agent.craft_posts(
            reviewer_output,
            skill_name,
            skill_config.get("description", ""),
            _summarize_feature_notes(skill_config),
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
        for tweet in new_tweets[:5]:
            snippet = tweet.get("snippet", "")
            suggested_reply = (
                f"{skill_name} lens: {snippet[:140].strip()} — "
                "Agree or disagree? I would add that focusing on one workflow compounds results."
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
            new_tweets=len(new_tweets),
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
