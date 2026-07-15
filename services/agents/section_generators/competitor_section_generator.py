from services.agents.section_generators.base_section_generator import BaseSectionGenerator
from services.schemas.insight import CompetitorIntelligence

class CompetitorSectionGenerator(BaseSectionGenerator):
    def __init__(self):
        super().__init__("Competitor Intelligence", CompetitorIntelligence)
