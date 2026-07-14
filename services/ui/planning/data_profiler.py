from services.research.models import ResearchContext

from ..schemas.data_profile_schema import DataProfile, SignalProfile

class DataProfiler:
    def profile(self, context: ResearchContext) -> DataProfile:
        """
        Profiles the available research data to determine what analytical signals
        are supported.
        """
        entity = context.entity
        profile = context.profile or context.company_profile
        financials = context.financials

        products = entity.products if entity else []
        services = entity.services if entity else []
        solutions = entity.solutions if entity and entity.solutions else None
        brands = entity.subsidiaries_or_brands if entity else []
        employee_count = getattr(profile.employee_count, "value", None) if profile and profile.employee_count else None
        headquarters = profile.headquarters if profile else None
        news = context.news or []
        leadership = context.leadership or []
        social_sentiment = context.social_sentiment

        has_identity = bool(entity and entity.entity and entity.entity.name)
        has_biz_arch = bool(products or services or (solutions and any(solutions.model_dump().values())))
        has_platform = has_biz_arch and (len(products) > 3 or len(services) > 3)
        has_brands = bool(brands)
        has_financials = bool(financials)

        geo_count = 0
        if entity and entity.entity and entity.entity.country:
            geo_count += 1
        if entity and entity.entity and entity.entity.headquarters:
            geo_count += 1

        solution_item_count = 0
        if solutions:
            solution_item_count = sum(len(items) for items in solutions.model_dump().values() if isinstance(items, list))

        return DataProfile(
            entity_identity=SignalProfile(
                available=has_identity,
                completeness=0.9 if has_identity else 0.0,
                confidence=entity.confidence if entity else 0.0,
                item_count=1 if has_identity else 0,
                evidence_paths=["entity.entity.name", "entity.entity.industry", "profile.overview"] if has_identity else [],
                signals=["name", "industry", "website"] if has_identity else [],
            ),
            company_scale=SignalProfile(
                available=employee_count is not None,
                completeness=0.7 if employee_count is not None else 0.0,
                confidence=0.8 if employee_count is not None else 0.0,
                item_count=1 if employee_count is not None else 0,
                evidence_paths=["profile.employee_count"] if employee_count is not None else [],
                signals=["employee_count"] if employee_count is not None else [],
            ),
            business_architecture=SignalProfile(
                available=has_biz_arch,
                completeness=1.0 if has_biz_arch else 0.0,
                confidence=0.85 if has_biz_arch else 0.0,
                item_count=len(products) + len(services) + solution_item_count,
                evidence_paths=["entity.products", "entity.services", "entity.solutions"] if has_biz_arch else [],
                signals=["products", "services", "solutions"] if has_biz_arch else [],
                metadata={
                    "product_count": len(products),
                    "service_count": len(services),
                    "solution_count": solution_item_count,
                },
            ),
            platform_structure=SignalProfile(
                available=has_platform,
                completeness=0.8 if has_platform else 0.0,
                confidence=0.8 if has_platform else 0.0,
                item_count=len(products) + len(services),
                evidence_paths=["entity.products", "entity.services"] if has_platform else [],
                signals=["multi-offering-platform"] if has_platform else [],
            ),
            brand_portfolio=SignalProfile(
                available=has_brands,
                completeness=0.8 if has_brands else 0.0,
                confidence=0.8 if has_brands else 0.0,
                item_count=len(brands),
                evidence_paths=["entity.subsidiaries_or_brands"] if has_brands else [],
                signals=["brands"] if has_brands else [],
            ),
            geographic_footprint=SignalProfile(
                available=geo_count > 0 or headquarters is not None,
                completeness=0.6 if geo_count > 0 or headquarters is not None else 0.0,
                confidence=0.7 if geo_count > 0 or headquarters is not None else 0.0,
                item_count=geo_count,
                evidence_paths=["entity.entity.country", "entity.entity.headquarters", "profile.headquarters"] if geo_count > 0 or headquarters is not None else [],
                signals=["country", "headquarters"] if geo_count > 0 or headquarters is not None else [],
            ),
            financial_history=SignalProfile(
                available=has_financials,
                completeness=0.8 if has_financials else 0.0,
                confidence=0.75 if has_financials else 0.0,
                item_count=sum(
                    1 for value in financials.model_dump().values()
                    if value not in (None, "N/A", [], {}, "")
                ) if financials else 0,
                evidence_paths=["financials"] if has_financials else [],
                signals=["financials"] if has_financials else [],
            ),
            news_intelligence=SignalProfile(
                available=bool(news),
                completeness=min(len(news) / 5.0, 1.0) if news else 0.0,
                confidence=0.7 if news else 0.0,
                item_count=len(news),
                evidence_paths=["news"] if news else [],
                signals=["news"] if news else [],
            ),
            leadership=SignalProfile(
                available=bool(leadership),
                completeness=min(len(leadership) / 3.0, 1.0) if leadership else 0.0,
                confidence=0.7 if leadership else 0.0,
                item_count=len(leadership),
                evidence_paths=["leadership"] if leadership else [],
                signals=["leadership"] if leadership else [],
            ),
            social_intelligence=SignalProfile(
                available=social_sentiment is not None,
                completeness=0.6 if social_sentiment is not None else 0.0,
                confidence=getattr(social_sentiment, "confidence", 0.0) if social_sentiment is not None else 0.0,
                item_count=1 if social_sentiment is not None else 0,
                evidence_paths=["social_sentiment"] if social_sentiment is not None else [],
                signals=["social_sentiment"] if social_sentiment is not None else [],
            ),
        )
