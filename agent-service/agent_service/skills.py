import json
from pathlib import Path
from typing import Any, Dict, List

from agent_service.database import DatabaseHandler


class SkillManager:
    def __init__(self, db: DatabaseHandler | None = None):
        self.db = db or DatabaseHandler()

    def _seed_path(self) -> Path:
        repo_root = Path(__file__).resolve().parents[2]
        return repo_root / "agent-service" / "skills_seed.json"

    def load_seed_skills(self) -> List[Dict[str, Any]]:
        seed_path = self._seed_path()
        if not seed_path.exists():
            raise FileNotFoundError(f"skills_seed.json not found at {seed_path}")
        with seed_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def seed_database(self) -> List[Dict[str, Any]]:
        skills = self.load_seed_skills()
        for skill in skills:
            self.db.upsert_skill(
                slug=skill["slug"],
                name=skill["name"],
                skill_type=skill["type"],
                status=skill.get("status", "active"),
                priority=skill.get("priority", 0.5),
                config_json=skill,
            )
        return skills

    def get_active_skills(self) -> List[Dict[str, Any]]:
        return self.db.get_active_skills()
