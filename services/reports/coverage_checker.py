from __future__ import annotations

from typing import List

from services.reports.models import CoverageResult


class CoverageChecker:
    def summarize(self, coverage_results: List[CoverageResult]) -> list[str]:
        gaps = []
        for result in coverage_results:
            if result.coverage_score < 0.5:
                gaps.append(f"{result.page_id}: limited evidence coverage ({result.coverage_score:.0%})")
        return gaps
