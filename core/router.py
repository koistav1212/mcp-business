import logging
from typing import Optional
from skills.base import BaseSkill
from registry.skill_registry import SkillRegistry

logger = logging.getLogger(__name__)

class AgentRouter:
    """
    Inspects user queries and routes them to the best-matching registered Skill.
    """
    def __init__(self, skill_registry: SkillRegistry):
        self.registry = skill_registry

    def route(self, query: str) -> Optional[BaseSkill]:
        """
        Scans registered skills and ranks them by query-to-metadata matching score.
        Returns the highest-scoring BaseSkill, or None if no confident match is found.
        """
        query_lower = query.lower()
        best_skill: Optional[BaseSkill] = None
        highest_score = 0

        for skill in self.registry.list_skills():
            score = 0
            
            # 1. Match against skill name segments
            name_segments = skill.name.replace("-", " ").replace("_", " ").split()
            for segment in name_segments:
                if segment in query_lower:
                    score += 5
            
            # 2. Match against description words
            desc_words = skill.description.lower().split()
            for word in desc_words:
                cleaned_word = word.strip(".,?!()")
                if len(cleaned_word) > 3 and cleaned_word in query_lower:
                    score += 1

            if score > highest_score:
                highest_score = score
                best_skill = skill

        # Route only if we have reasonable matching confidence
        if highest_score < 2:
            logger.info("No matching skill found above routing threshold.")
            return None

        logger.info(f"Routed query to skill '{best_skill.name}' with match score {highest_score}")
        return best_skill
