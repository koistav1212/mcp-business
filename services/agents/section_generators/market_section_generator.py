from services.agents.section_generators.base_section_generator import BaseSectionGenerator
from services.schemas.insight import ProductAgentOutput

class MarketSectionGenerator(BaseSectionGenerator):
    def __init__(self):
        super().__init__("Product and Market Intelligence", ProductAgentOutput)
