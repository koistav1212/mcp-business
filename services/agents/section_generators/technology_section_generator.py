from services.agents.section_generators.base_section_generator import BaseSectionGenerator
from services.schemas.insight import TechnologyIntelligence

class TechnologySectionGenerator(BaseSectionGenerator):
    def __init__(self):
        super().__init__("Technology Intelligence", TechnologyIntelligence)
