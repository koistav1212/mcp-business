from services.agents.section_generators.base_section_generator import BaseSectionGenerator
from services.schemas.insight import NewsIntelligence

class RiskSectionGenerator(BaseSectionGenerator):
    def __init__(self):
        super().__init__("News and Risk Intelligence", NewsIntelligence)
