from __future__ import annotations

import re


class ReportEditor:
    def polish(self, markdown: str) -> str:
        cleaned = markdown.replace("\r\n", "\n").strip()
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()
