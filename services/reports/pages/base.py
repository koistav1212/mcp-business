from __future__ import annotations

import json
import re
from typing import Any, Dict

from services.llm.provider_router import ProviderRouter
from services.reports.models import GeneratedPage, ReportPageSpec


def sanitize_markdown(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = text.replace("Thinking Process:", "").strip()
    return text.strip()


class BasePageAgent:
    def __init__(self, agent_name: str, system_prompt: str):
        self.agent_name = agent_name
        self.system_prompt = system_prompt

    async def generate(self, spec: ReportPageSpec, page_context: Dict[str, Any]) -> GeneratedPage:
        markdown = self.render_fallback(page_context)
        try:
            prompt = json.dumps(page_context, default=str)
            result = await ProviderRouter.generate_text(
                agent_name=self.agent_name,
                system_prompt=self.system_prompt,
                user_prompt=prompt,
            )
            cleaned = sanitize_markdown(result)
            if cleaned:
                markdown = cleaned
        except Exception:
            pass

        return GeneratedPage(
            page_id=spec.page_id,
            title=spec.title,
            markdown=markdown,
            context_keys=sorted(page_context.keys()),
        )

    def render_fallback(self, page_context: Dict[str, Any]) -> str:
        lines = []
        for key, value in page_context.items():
            if value in (None, "", [], {}):
                continue
            if isinstance(value, dict):
                lines.append(f"- **{key}**: available")
            else:
                lines.append(f"- **{key}**: {value}")
        body = "\n".join(lines) if lines else "- Evidence for this page is limited in the current run."
        return f"### {self.agent_name.replace('_', ' ').title()}\n{body}"
