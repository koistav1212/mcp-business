from services.agents.section_generators.base_section_generator import BaseSectionGenerator
from services.schemas.insight import FinancialAgentOutput

class FinancialSectionGenerator(BaseSectionGenerator):
    def __init__(self):
        super().__init__("Financials", FinancialAgentOutput)

    def build_prompt(self, entity_name: str) -> str:
        base_prompt = super().build_prompt(entity_name)
        return base_prompt + "\nFor 'trend_analysis', feed the numerical data provided to formulate a comprehensive analysis of the company's financial trends over time, highlighting positive momentum or declining metrics."
