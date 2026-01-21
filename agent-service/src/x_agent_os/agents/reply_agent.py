import json
from typing import Any, Dict, List, Optional

import google.generativeai as genai

from x_agent_os.config import GOOGLE_API_KEY
from x_agent_os.database import DatabaseHandler
from x_agent_os.skills import SkillManager


class ReplyAgent:
    def __init__(self, db: Optional[DatabaseHandler] = None):
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not configured.")
        genai.configure(api_key=GOOGLE_API_KEY)
        self.db = db or DatabaseHandler()
        self.skill_manager = SkillManager(self.db)
        self.model = genai.GenerativeModel("gemini-3-flash-preview")

    def _get_personal_brand(self) -> Dict[str, Any]:
        skill = self.db.get_skill_by_slug("personal_brand")
        if skill:
            return skill["config_json"]
        seed = self.skill_manager.load_seed_skills()
        for item in seed:
            if item.get("slug") == "personal_brand":
                return item
        return {}

    def _collect_style_examples(self, limit: int = 5) -> List[str]:
        posts = self.db.list_recent_posts(limit=limit)
        examples = []
        for post in posts:
            content = post.get("published_content") or post.get("draft_content") or ""
            if content:
                examples.append(content.strip())
        return examples

    def _collect_creator_personas(self, limit: int = 2) -> List[Dict[str, Any]]:
        personas = self.db.list_creator_personas(active_only=True)
        persona_context = []
        for persona in personas[:limit]:
            handle = persona.get("handle")
            run = self.db.get_latest_creator_persona_run(handle)
            posts = self.db.list_creator_persona_posts(persona["id"], limit=3)
            persona_context.append(
                {
                    "handle": handle,
                    "summary": run.get("summary_json") if run else None,
                    "top_posts": [post.get("content") for post in posts],
                }
            )
        return persona_context

    def generate_reply_for_conversation(self, conversation_id: int) -> str:
        conversation = self.db.get_conversation_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found.")

        brand = self._get_personal_brand()
        examples = self._collect_style_examples(limit=3)
        personas = self._collect_creator_personas(limit=2)

        context = {
            "brand_summary": {
                "values": brand.get("values", []),
                "voice_notes": brand.get("voice_notes", []),
                "lexicon": brand.get("lexicon", []),
                "avoid": brand.get("avoid", []),
                "pillars": brand.get("pillars", []),
                "style_constraints": brand.get("style_constraints", []),
            },
            "reply_style": brand.get("reply_style"),
            "skill_slug": conversation.get("skill_slug"),
            "tweet_snippet": conversation.get("snippet"),
            "tweet_reason": conversation.get("reason"),
            "author_handle": conversation.get("author_handle"),
            "tweet_url": conversation.get("x_tweet_url"),
            "recent_posts": examples,
            "creator_personas": personas,
        }

        prompt_text = (
            "You are an assistant generating a reply in the author's personal brand voice. "
            "Follow the brand manifesto and prioritize clarity, leverage, and direct advice. "
            "Output only the reply text. No labels or JSON.\n\n"
            "Use the following context to craft a concise reply (1-3 short sentences). "
            "Reference the tweet snippet directly, add one concrete insight, and end with a precise question.\n\n"
            f"Context:\n{json.dumps(context, indent=2)}"
        )

        response = self.model.generate_content(prompt_text)
        if not response.parts:
            raise RuntimeError("Empty response from reply agent.")
        reply_text = response.text.strip()
        self.db.update_conversation_reply(conversation_id, reply_text)
        return reply_text
