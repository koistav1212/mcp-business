import logging
from typing import Dict, List, Optional
from skills.base import BaseSkill

logger = logging.getLogger(__name__)

class SkillRegistry:
    """
    Registry for agent Skills. Enables dynamic discovery and selection of multi-step workflows.
    """
    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        """Register a single skill instance."""
        if skill.name in self._skills:
            logger.warning(f"Overwriting already registered skill: {skill.name}")
        self._skills[skill.name] = skill
        logger.info(f"Registered skill in registry: {skill.name}")

    def get(self, name: str) -> Optional[BaseSkill]:
        """Retrieve a skill by its unique name."""
        return self._skills.get(name)

    def list_skills(self) -> List[BaseSkill]:
        """List all registered skill instances."""
        return list(self._skills.values())

    def list_skill_names(self) -> List[str]:
        """List all registered skill names."""
        return list(self._skills.keys())

# Global singleton instance
skill_registry = SkillRegistry()
