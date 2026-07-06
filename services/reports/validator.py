from __future__ import annotations

from typing import List

from services.reports.models import GeneratedPage


class ReportValidator:
    def validate(self, pages: List[GeneratedPage]) -> list[str]:
        issues = []
        for page in pages:
            if not page.markdown.strip():
                issues.append(f"{page.page_id}: empty page output")
        return issues
