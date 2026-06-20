from services.research.models import IndustryContext, IntentPlan


class IndustryClassifier:
    INDUSTRIES = {
        "banking": ({"bank", "lending", "fintech", "insurance"}, ["deposits", "loan growth", "asset quality", "capital adequacy"]),
        "metals": ({"steel", "aluminium", "mining", "commodity"}, ["realizations", "volume", "EBITDA per tonne", "net debt"]),
        "construction": ({"construction", "infrastructure", "engineering", "real estate"}, ["order book", "project pipeline", "execution", "government exposure"]),
        "software": ({"software", "saas", "cloud", "crm", "technology", "ai"}, ["recurring revenue", "retention", "product ecosystem", "sales efficiency"]),
        "semiconductors": ({"semiconductor", "chip", "gpu", "nvidia"}, ["data center growth", "gross margin", "ecosystem", "supply constraints"]),
    }

    def classify(self, intent: IntentPlan, company_overview: str = "") -> IndustryContext:
        text = f"{intent.primary_goal} {intent.industry_focus} {company_overview}".lower()
        for industry, (keywords, metrics) in self.INDUSTRIES.items():
            if any(keyword in text for keyword in keywords):
                return IndustryContext(
                    industry=industry,
                    confidence=0.88,
                    key_metrics=metrics,
                    strategic_themes=self._themes(industry),
                )
        return IndustryContext(
            industry="general",
            confidence=0.55,
            key_metrics=["growth", "profitability", "competitive position", "execution risk"],
            strategic_themes=["market position", "operating performance", "risk"],
        )

    @staticmethod
    def _themes(industry: str):
        return {
            "banking": ["funding quality", "credit risk", "regulatory resilience"],
            "metals": ["commodity cycle", "cost position", "capacity expansion"],
            "construction": ["project conversion", "working capital", "policy exposure"],
            "software": ["product moat", "customer retention", "go-to-market efficiency"],
            "semiconductors": ["compute demand", "platform moat", "competitive supply"],
        }[industry]
