from services.agents.section_generators.base_section_generator import BaseSectionGenerator
from services.schemas.insight import SocialAgentOutput

class SocialSectionGenerator(BaseSectionGenerator):
    def __init__(self):
        super().__init__("Social Intelligence", SocialAgentOutput)
