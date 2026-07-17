from services.agents.section_generators.base_section_generator import BaseSectionGenerator
from services.schemas.insight import OperationsAgentOutput

class OperationsSectionGenerator(BaseSectionGenerator):
    def __init__(self):
        super().__init__("Operations Intelligence", OperationsAgentOutput)
