from __future__ import annotations

from typing import List

from services.reports.models import GeneratedPage


class ReportComposer:
    def compose(self, pages: List[GeneratedPage]) -> str:
        blocks = []
        for page in pages:
            blocks.append(f"## {page.title}\n{page.markdown.strip()}")
        return "\n\n".join(blocks).strip()
