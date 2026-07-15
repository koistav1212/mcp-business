import re
import uuid
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from services.schemas.insight import ResearchContext, SourcedValue

from ..schemas.component_plan_schema import PlannedComponent, ComponentPlan
from ..schemas.data_profile_schema import DataProfile
from ..schemas.insight_schema import InsightCandidate, InsightPlan, ExecutiveQuestion
from ..schemas.ui_schema import UISchema, PageSchema, ComponentSchema, ExecutiveTakeaway, PageData


class UnsupportedComponentError(ValueError):
    pass

class PageComposer:
    def __init__(self) -> None:
        self._composers = {
            "ExecutiveHero": self._compose_executive_hero,
            "MetricStrip": self._compose_metric_strip,
            "BusinessArchitectureMap": self._compose_business_architecture,
            "PlatformStackMap": self._compose_platform_stack,
            "StrategicPositionCard": self._compose_strategic_position,
            "FactMatrix": self._compose_fact_matrix,
            "ExecutiveTakeaway": self._compose_executive_takeaway_component,
            "FinancialHealthScorecard": self._compose_financial_health_scorecard,
            "NewsTimeline": self._compose_news_timeline,
            "RiskMatrix": self._compose_risk_matrix,
            "SentimentTimeline": self._compose_sentiment_timeline,
            "KnowledgeGraphViewer": self._compose_knowledge_graph,
        }

    def compose(
        self,
        context: ResearchContext,
        data_profile: DataProfile,
        insight_plan: InsightPlan,
        component_plan: ComponentPlan,
    ) -> UISchema:
        """
        Composes the final page schemas by mapping components to their respective pages based on executive questions.
        """
        company_name = self._company_name(context)
        
        pages_data: List[PageData] = []
        
        for idx, question in enumerate(insight_plan.executive_questions):
            page = PageSchema(
                page_number=idx + 1,
                page_type="executive_company_snapshot" if idx == 0 else "analytical_deep_dive",
                title=f"{company_name} - {question.question}",
                executive_question=question.question,
                executive_headline=self._build_page_headline(context, insight_plan) if idx == 0 else "",
                image_search_query=self._build_image_query(context) if idx == 0 else None,
            )
            
            components: List[ComponentSchema] = []
            
            # Filter components for this page
            page_components = [c for c in component_plan.selected_components if c.executive_question_id == question.id]
            ordered_components = sorted(page_components, key=lambda c: c.priority)
            
            for planned_component in ordered_components:
                composer = self._composers.get(planned_component.component_type)
                if composer is None:
                    continue # Skip unsupported components instead of crashing
                components.append(
                    composer(
                        planned_component=planned_component,
                        context=context,
                        data_profile=data_profile,
                        insight_plan=insight_plan,
                    )
                )
                
            pages_data.append(PageData(page=page, components=components))

        takeaway = self._build_executive_takeaway(insight_plan)

        return UISchema(
            pages=pages_data,
            executive_takeaway=takeaway
        )

    def _compose_executive_hero(
        self,
        planned_component: PlannedComponent,
        context: ResearchContext,
        data_profile: DataProfile,
        insight_plan: InsightPlan,
    ) -> ComponentSchema:
        entity = context.entity.entity if context.entity else None
        profile = context.profile or context.company_profile
        derived_content = self._remove_empty(
            {
                "company_name": entity.name if entity else self._company_name(context),
                "ticker": entity.ticker if entity else None,
                "exchange": entity.exchange if entity else None,
                "industry": entity.industry if entity else None,
                "subindustry": entity.subindustry if entity else None,
                "headline": self._build_page_headline(context, insight_plan),
                "website": entity.website if entity else self._extract_value(profile.website if profile else None),
            }
        )
        return self._build_component(
            planned_component,
            context,
            insight_plan,
            title="Executive Hero",
            bindings=[
                "entity.entity.name",
                "entity.entity.ticker",
                "entity.entity.exchange",
                "entity.entity.industry",
                "entity.entity.subindustry",
                "entity.entity.website",
                "profile.overview",
            ],
            derived_content=derived_content,
            default_evidence=["entity.entity.name", "entity.entity.industry", "profile.overview"],
        )

    def _compose_metric_strip(
        self,
        planned_component: PlannedComponent,
        context: ResearchContext,
        data_profile: DataProfile,
        insight_plan: InsightPlan,
    ) -> ComponentSchema:
        entity = context.entity.entity if context.entity else None
        profile = context.profile or context.company_profile
        metrics = []
        candidates = [
            ("Employees", self._extract_value(profile.employee_count if profile else None), "integer", "profile.employee_count"),
            ("Founded", entity.founded if entity else None, "integer", "entity.entity.founded"),
            ("Ticker", entity.ticker if entity else None, "text", "entity.entity.ticker"),
            ("Exchange", entity.exchange if entity else None, "text", "entity.entity.exchange"),
            ("Headquarters", self._format_headquarters(entity.headquarters if entity else None), "text", "entity.entity.headquarters"),
            ("Country", entity.country if entity else None, "text", "entity.entity.country"),
            ("Parent Company", entity.parent_company if entity else None, "text", "entity.entity.parent_company"),
            ("Brands", len(context.entity.subsidiaries_or_brands) if context.entity and context.entity.subsidiaries_or_brands else None, "integer", "entity.subsidiaries_or_brands"),
            ("Architecture Groups", self._architecture_group_count(context), "integer", "entity.products"),
        ]
        for label, value, fmt, path in candidates:
            if self._is_present(value):
                metrics.append({"label": label, "value": value, "format": fmt, "evidence_path": path})
            if len(metrics) == 5:
                break
        metrics = metrics[:5]
        return self._build_component(
            planned_component,
            context,
            insight_plan,
            title="Metric Strip",
            bindings=[metric["evidence_path"] for metric in metrics],
            derived_content={"metrics": [{"label": metric["label"], "value": metric["value"], "format": metric["format"]} for metric in metrics[:5]]},
            default_evidence=[metric["evidence_path"] for metric in metrics],
        )

    def _compose_business_architecture(
        self,
        planned_component: PlannedComponent,
        context: ResearchContext,
        data_profile: DataProfile,
        insight_plan: InsightPlan,
    ) -> ComponentSchema:
        groups = self._build_architecture_groups(context)
        return self._build_component(
            planned_component,
            context,
            insight_plan,
            title="Business Architecture",
            bindings=["entity.products", "entity.services", "entity.solutions", "profile.overview"],
            derived_content={"groups": groups},
            default_evidence=["entity.products", "entity.services", "entity.solutions", "profile.overview"],
        )

    def _compose_platform_stack(
        self,
        planned_component: PlannedComponent,
        context: ResearchContext,
        data_profile: DataProfile,
        insight_plan: InsightPlan,
    ) -> ComponentSchema:
        groups = self._build_architecture_groups(context)
        return self._build_component(
            planned_component,
            context,
            insight_plan,
            title="Platform Stack",
            bindings=["entity.products", "entity.services", "entity.solutions"],
            derived_content={"layers": groups[:4]},
            default_evidence=["entity.products", "entity.services", "entity.solutions"],
        )

    def _compose_strategic_position(
        self,
        planned_component: PlannedComponent,
        context: ResearchContext,
        data_profile: DataProfile,
        insight_plan: InsightPlan,
    ) -> ComponentSchema:
        entity = context.entity.entity if context.entity else None
        profile = context.profile or context.company_profile
        linked_insights = self._planned_insights(planned_component, insight_plan)
        assessment = linked_insights[0].statement if linked_insights else self._short_overview(profile.overview if profile else None)
        derived_content = self._remove_empty(
            {
                "position_label": entity.industry if entity and entity.industry else "Strategic Position",
                "position_type": "platform" if data_profile.technology else "operating model",
                "strategic_layers": [group["label"] for group in self._build_architecture_groups(context)[:3]],
                "short_assessment": assessment,
            }
        )
        return self._build_component(
            planned_component,
            context,
            insight_plan,
            title="Strategic Position",
            bindings=["profile.overview", "entity.products", "entity.services", "entity.solutions", "entity.entity.industry"],
            derived_content=derived_content,
            default_evidence=["profile.overview", "entity.products", "entity.services", "entity.solutions"],
        )

    def _compose_fact_matrix(
        self,
        planned_component: PlannedComponent,
        context: ResearchContext,
        data_profile: DataProfile,
        insight_plan: InsightPlan,
    ) -> ComponentSchema:
        entity = context.entity.entity if context.entity else None
        facts = []
        candidates = [
            ("Company", entity.name if entity else self._company_name(context), "entity.entity.name"),
            ("Industry", entity.industry if entity else None, "entity.entity.industry"),
            ("Subindustry", entity.subindustry if entity else None, "entity.entity.subindustry"),
            ("Website", entity.website if entity else None, "entity.entity.website"),
            ("Country", entity.country if entity else None, "entity.entity.country"),
            ("Employees", self._extract_value((context.profile or context.company_profile).employee_count) if (context.profile or context.company_profile) and (context.profile or context.company_profile).employee_count else None, "profile.employee_count"),
        ]
        for label, value, path in candidates:
            if self._is_present(value):
                facts.append({"label": label, "value": value})
        bindings = [path for _, value, path in candidates if self._is_present(value)]
        return self._build_component(
            planned_component,
            context,
            insight_plan,
            title="Fact Matrix",
            bindings=bindings,
            derived_content={"facts": facts[:6]},
            default_evidence=bindings,
        )

    def _compose_executive_takeaway_component(
        self,
        planned_component: PlannedComponent,
        context: ResearchContext,
        data_profile: DataProfile,
        insight_plan: InsightPlan,
    ) -> ComponentSchema:
        takeaway = self._build_executive_takeaway(insight_plan)
        return self._build_component(
            planned_component,
            context,
            insight_plan,
            title="Executive Takeaway",
            bindings=takeaway.evidence_paths,
            derived_content={"text": takeaway.text},
            default_evidence=takeaway.evidence_paths,
        )

    def _compose_financial_health_scorecard(self, planned_component, context, data_profile, insight_plan):
        return self._build_component(
            planned_component, context, insight_plan, title="Financial Health Scorecard",
            bindings=["financials"], derived_content={}, default_evidence=[]
)

    def _compose_knowledge_graph(self, planned_component: PlannedComponent, context: ResearchContext, *args, **kwargs) -> ComponentSchema:
        graph = context.evidence_graph
        if not graph or not graph.nodes:
            return self._build_component(planned_component, context, kwargs.get("insight_plan"), title="Knowledge Graph Viewer", bindings=[], derived_content={}, default_evidence=[])
            
        derived_content = {
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges) if hasattr(graph, 'edges') and graph.edges else 0,
            "clusters": ["Products", "Executives", "Competitors", "Technologies", "Financial Metrics"]
        }
        
        return self._build_component(
            planned_component,
            context,
            kwargs.get("insight_plan"),
            title="Corporate Knowledge Graph",
            bindings=["evidence_graph.nodes"],
            derived_content=derived_content,
            default_evidence=["evidence_graph.nodes"]
        )

    def _compose_news_timeline(self, planned_component: PlannedComponent, context: ResearchContext, *args, **kwargs) -> ComponentSchema:
        news = context.news
        if not news:
            return self._build_component(planned_component, context, kwargs.get("insight_plan"), title="News Timeline", bindings=[], derived_content={}, default_evidence=[])
            
        timeline = []
        sources = set()
        for n in news[:10]:
            val = getattr(n, "value", n)
            if isinstance(val, dict):
                date = val.get("date")
                title = val.get("title")
                summary = val.get("summary", val.get("snippet"))
                sentiment = val.get("sentiment", "neutral")
                source = val.get("source")
            else:
                date = getattr(val, "date", None)
                title = getattr(val, "title", None)
                summary = getattr(val, "summary", getattr(val, "snippet", None))
                sentiment = getattr(val, "sentiment", "neutral")
                source = getattr(val, "source", None)
            
            if not source and getattr(n, "source_ids", None):
                source = n.source_ids[0] if n.source_ids else None
                
            if source:
                sources.add(source)
                
            timeline.append({
                "date": date,
                "title": title,
                "summary": summary,
                "sentiment": sentiment
            })
            
        derived_content = {
            "event_count": len(news),
            "sources": list(sources),
            "timeline": timeline
        }
        
        return self._build_component(
            planned_component,
            context,
            kwargs.get("insight_plan"),
            title="Major Events & News Timeline",
            bindings=["news"],
            derived_content=derived_content,
            default_evidence=["news"]
        )

    def _compose_sentiment_timeline(self, planned_component, context, data_profile, insight_plan):
        return self._build_component(
            planned_component, context, insight_plan, title="Sentiment Timeline",
            bindings=["sentiment"], derived_content={}, default_evidence=[]
        )

    def _compose_risk_matrix(self, planned_component: PlannedComponent, context: ResearchContext, *args, **kwargs) -> ComponentSchema:
        return self._build_component(
            planned_component,
            context,
            kwargs.get("insight_plan"),
            title="Risk Matrix",
            bindings=["risk_factors"],
            derived_content={},
            default_evidence=["risk_factors"]
        )


    def _build_component(
        self,
        planned_component: PlannedComponent,
        context: ResearchContext,
        insight_plan: InsightPlan,
        title: str,
        bindings: List[str],
        derived_content: Dict[str, Any],
        default_evidence: List[str],
    ) -> ComponentSchema:
        question = self._question_text(insight_plan, planned_component.executive_question_id)
        evidence = self._evidence_paths(planned_component, insight_plan, default_evidence)
        return ComponentSchema(
            id=str(uuid.uuid4()),
            type=planned_component.component_type,
            title=title,
            span=planned_component.span,
            analytical_question=question,
            bindings=self._dedupe(bindings),
            derived_content=self._remove_empty(derived_content),
            evidence_paths=self._dedupe(evidence),
        )

    def _build_page_headline(self, context: ResearchContext, insight_plan: InsightPlan) -> str:
        top_insight = next((insight.statement for insight in insight_plan.insight_candidates if insight.statement), None)
        if top_insight:
            return self._trim_sentence(top_insight, max_words=18)
        profile = context.profile or context.company_profile
        if profile and profile.overview:
            return self._trim_sentence(profile.overview, max_words=18)
        return f"{self._company_name(context)} strategic snapshot"

    def _build_image_query(self, context: ResearchContext) -> Optional[str]:
        entity = context.entity.entity if context.entity else None
        if not entity:
            return None
        keywords = [entity.name, entity.industry, entity.subindustry]
        products = [product.name for product in (context.entity.products[:2] if context.entity else [])]
        tokens = [token for token in keywords + products if token]
        return " ".join(tokens[:5]) if tokens else None

    def _build_executive_takeaway(self, insight_plan: InsightPlan) -> ExecutiveTakeaway:
        statements = [insight.statement.strip() for insight in insight_plan.insight_candidates if insight.statement.strip()]
        evidence_paths = self._dedupe(
            [path for insight in insight_plan.insight_candidates for path in insight.evidence_paths]
        )
        if statements:
            text = self._trim_sentence(" ".join(statements[:2]), max_words=40)
        else:
            text = "Available evidence supports a clear executive snapshot, though some strategic detail remains limited."
        return ExecutiveTakeaway(text=text, evidence_paths=evidence_paths)

    def _question_text(self, insight_plan: InsightPlan, question_id: str) -> str:
        for question in insight_plan.executive_questions:
            if question.id == question_id:
                return question.question
        return question_id

    def _planned_insights(self, planned_component: PlannedComponent, insight_plan: InsightPlan) -> List[InsightCandidate]:
        insight_ids = set(planned_component.insight_ids)
        return [insight for insight in insight_plan.insight_candidates if insight.id in insight_ids]

    def _evidence_paths(
        self,
        planned_component: PlannedComponent,
        insight_plan: InsightPlan,
        default_evidence: List[str],
    ) -> List[str]:
        insight_paths = [
            path
            for insight in self._planned_insights(planned_component, insight_plan)
            for path in insight.evidence_paths
        ]
        question_paths = []
        for question in insight_plan.executive_questions:
            if question.id == planned_component.executive_question_id:
                question_paths.extend(question.evidence_paths)
                break
        return self._dedupe(default_evidence + insight_paths + question_paths)

    def _build_architecture_groups(self, context: ResearchContext) -> List[Dict[str, Any]]:
        groups: "OrderedDict[str, List[str]]" = OrderedDict()
        for product in context.entity.products if context.entity else []:
            label = self._normalize_label(product.category) or "Products"
            groups.setdefault(label, [])
            groups[label].append(product.name)
        for service in context.entity.services if context.entity else []:
            label = self._infer_service_group(service)
            groups.setdefault(label, [])
            groups[label].append(service)
        solutions = context.entity.solutions if context.entity else None
        if solutions:
            for key, items in solutions.model_dump().items():
                if not isinstance(items, list) or not items:
                    continue
                label = self._normalize_label(key)
                groups.setdefault(label, [])
                groups[label].extend(items)

        normalized_groups = []
        for label, items in groups.items():
            clean_items = self._dedupe([self._clean_label(item) for item in items if self._is_present(item)])[:5]
            if clean_items:
                normalized_groups.append({"label": label, "items": clean_items})
            if len(normalized_groups) == 5:
                break

        if normalized_groups:
            return normalized_groups

        overview = (context.profile or context.company_profile).overview if (context.profile or context.company_profile) else ""
        if overview:
            phrases = self._extract_keywords(overview)
            if phrases:
                return [{"label": "Core Business", "items": phrases[:5]}]
        return [{"label": "Core Business", "items": [self._company_name(context)]}]

    def _architecture_group_count(self, context: ResearchContext) -> int:
        return len(self._build_architecture_groups(context))

    def _company_name(self, context: ResearchContext) -> str:
        if context.entity and context.entity.entity and context.entity.entity.name:
            return context.entity.entity.name
        if context.profile and context.profile.name:
            return context.profile.name
        return "Unknown Company"

    def _short_overview(self, overview: Optional[str]) -> str:
        if not overview:
            return "Business positioning inferred from available company evidence."
        return self._trim_sentence(overview, max_words=24)

    def _format_headquarters(self, headquarters: Any) -> Optional[str]:
        if not headquarters:
            return None
        if isinstance(headquarters, dict):
            parts = [headquarters.get("city"), headquarters.get("state"), headquarters.get("country")]
        else:
            parts = [getattr(headquarters, "city", None), getattr(headquarters, "state", None), getattr(headquarters, "country", None)]
        formatted = ", ".join(part for part in parts if part)
        return formatted or None

    def _extract_value(self, value: Any) -> Any:
        if isinstance(value, SourcedValue):
            return value.value
        return getattr(value, "value", value)

    def _normalize_label(self, label: str) -> str:
        return self._clean_label(label.replace("_", " ")).title()

    def _clean_label(self, label: str) -> str:
        return re.sub(r"\s+", " ", str(label)).strip()

    def _infer_service_group(self, service: str) -> str:
        service_lower = service.lower()
        if any(token in service_lower for token in ("platform", "cloud", "infrastructure", "network")):
            return "Infrastructure"
        if any(token in service_lower for token in ("consult", "support", "services")):
            return "Services"
        if any(token in service_lower for token in ("software", "developer", "api")):
            return "Software"
        return "Services"

    def _trim_sentence(self, text: str, max_words: int) -> str:
        words = self._clean_label(text).split()
        if len(words) <= max_words:
            return " ".join(words)
        return " ".join(words[:max_words]).rstrip(",.;:") + "..."

    def _extract_keywords(self, text: str) -> List[str]:
        tokens = re.split(r"[,.;/]", text)
        keywords = []
        for token in tokens:
            cleaned = self._clean_label(token)
            if 2 <= len(cleaned.split()) <= 5:
                keywords.append(cleaned)
        return self._dedupe(keywords)

    def _remove_empty(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: self._remove_empty(item)
                for key, item in value.items()
                if self._is_present(self._remove_empty(item))
            }
        if isinstance(value, list):
            cleaned = [self._remove_empty(item) for item in value]
            return [item for item in cleaned if self._is_present(item)]
        return value

    def _is_present(self, value: Any) -> bool:
        return value not in (None, "", "N/A", [], {}, ())

    def _dedupe(self, items: List[Any]) -> List[Any]:
        seen = set()
        deduped = []
        for item in items:
            if item in seen or not self._is_present(item):
                continue
            seen.add(item)
            deduped.append(item)
        return deduped
