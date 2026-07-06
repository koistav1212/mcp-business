from __future__ import annotations

from typing import List

from services.reports.models import GeneratedPage


class ReportCritic:
    def review(self, pages: List[GeneratedPage]) -> dict:
        issues = []
        titles = {page.title for page in pages if page.markdown.strip()}
        if "Executive Summary" not in titles:
            issues.append("Missing executive summary page.")
        if len(pages) < 5:
            issues.append("Report has fewer than five pages.")
        repeated = set()
        seen = set()
        for page in pages:
            body = page.markdown.strip()
            if body in seen:
                repeated.add(page.page_id)
            seen.add(body)
        for page_id in sorted(repeated):
            issues.append(f"Repeated content detected in page '{page_id}'.")
        score = max(0.0, 1.0 - (0.1 * len(issues)))
        return {"score": score, "issues": issues}
