import json
import logging
import asyncio
from typing import Dict, Any, List

from services.llm.provider_router import ProviderRouter
from core.config import settings

logger = logging.getLogger("uvicorn.error")

class PageComposerAgent:
    """
    Deterministically iterates over the 3.0-final UI contract's report_pages and widgets.
    For each widget, it extracts the relevant bounded section data and asks the LLM
    to precisely format that data into the required UI data structure.
    This guarantees the exact page structure while flexibly mapping data fields.
    """

    def __init__(self):
        self.contract_path = "services/config/pipeline_v3_contract.json"
        
    def _load_contract(self) -> Dict[str, Any]:
        try:
            with open(self.contract_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load UI contract: {e}")
            return {}

    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        contract = self._load_contract()
        report_pages = contract.get("report_pages", [])
        if not report_pages:
            logger.warning("No report_pages found in UI contract.")
            return {"report_pages": []}

        composed_pages = []
        
        # We can process widgets in parallel to save time, but bounded by concurrency
        sem = asyncio.Semaphore(2)

        async def _populate_widget(widget: Dict[str, Any], page_id: str) -> Dict[str, Any]:
            async with sem:
                bound_section_name = widget.get("data_binding", {}).get("bound_section", "")
                
                # Resolve the section data
                section_data = {}
                if bound_section_name == "entity_extraction" or bound_section_name == "entity_extraction.output":
                    section_data = context.get("entity", {})
                elif bound_section_name == "synthesizer":
                    section_data = context.get("narratives", {})
                elif bound_section_name == "critic_agent":
                    section_data = context.get("critic_evaluation", {})
                elif "section_generation[" in bound_section_name:
                    # e.g. section_generation[Financials]
                    sec_name = bound_section_name.split("[")[1].split("]")[0]
                    section_data = context.get("sections", {}).get(sec_name, {})
                elif bound_section_name == "section_generation:*":
                    section_data = context.get("sections", {})
                elif bound_section_name == "company_provider":
                    section_data = {
                        "entity": context.get("entity", {}),
                        "financials": context.get("sections", {}).get("Financials", {})
                    }
                else:
                    # Generic fallback
                    section_data = context
                    
                # We also inject validated signals if requested
                if "validated_signals" in str(widget.get("data_keys", [])):
                    section_data["validated_signals"] = context.get("validated_signals", [])

                system_instruction = (
                    "You are a UI Data Binder. Your task is to extract data from the provided 'Context Data' "
                    "and format it EXACTLY according to the 'Requested Data Keys' for this UI widget.\n"
                    "Do NOT invent or infer any business facts. Only use the data provided. "
                    "If the data is completely missing, return empty objects or nulls according to the schema.\n"
                    "Return ONLY a JSON object containing the mapped keys."
                )

                payload = {
                    "widget_component": widget.get("component"),
                    "requested_data_keys": widget.get("data_keys", []),
                    "context_data": section_data
                }
                
                prompt = f"Bind Data:\n{json.dumps(payload, default=str)[:12000]}"
                
                try:
                    mapped_data = await ProviderRouter.generate_json(
                        agent_name="page_composer",
                        system_prompt=system_instruction,
                        user_prompt=prompt
                    )
                except Exception as e:
                    logger.error(f"PageComposer widget binding failed: {e}")
                    mapped_data = {}
                
                # Add a 2-second delay to gently pace the requests and prevent 429 rate limits
                await asyncio.sleep(2)
                
                # Return the populated widget
                populated_widget = widget.copy()
                populated_widget["data"] = mapped_data
                return populated_widget

        for page in report_pages:
            logger.info(f"Composing UI Page: {page.get('page_title')}")
            widgets = page.get("widgets", [])
            
            tasks = [_populate_widget(w, page.get("page_id")) for w in widgets]
            populated_widgets = await asyncio.gather(*tasks)
            
            composed_page = page.copy()
            composed_page["widgets"] = populated_widgets
            composed_pages.append(composed_page)

        return {"report_pages": composed_pages}
