from typing import Any, Dict

from services.research.models import ResearchContext

from ..schemas.ui_schema import UISchema, UIValidation

class UIValidator:
    def validate(self, ui_schema: UISchema, context: ResearchContext) -> UIValidation:
        """
        Validates the generated UI schema against data constraints.
        """
        component_count = len(ui_schema.components)

        types_seen = set()
        duplicates = []
        for c in ui_schema.components:
            if c.type in types_seen:
                duplicates.append(c.type)
            types_seen.add(c.type)

        null_values_rendered = any(self._contains_nullish(component.derived_content) for component in ui_schema.components)
        raw_duplicate_products_rendered = any(self._contains_duplicate_strings(component.derived_content) for component in ui_schema.components)
        biography_style_detected = len(ui_schema.page.executive_headline.split()) > 24 or len(ui_schema.executive_takeaway.text.split()) > 60
        all_claims_traceable = all(
            bool(component.evidence_paths) for component in ui_schema.components
        ) and bool(ui_schema.executive_takeaway.evidence_paths)

        passed = not any(
            [
                duplicates,
                null_values_rendered,
                raw_duplicate_products_rendered,
                biography_style_detected,
                not all_claims_traceable,
            ]
        )

        return UIValidation(
            component_count=component_count,
            duplicate_components=duplicates,
            null_values_rendered=null_values_rendered,
            raw_duplicate_products_rendered=raw_duplicate_products_rendered,
            biography_style_detected=biography_style_detected,
            all_claims_traceable=all_claims_traceable,
            passed=passed
        )

    def _contains_nullish(self, value: Any) -> bool:
        if value in (None, "", "N/A"):
            return True
        if isinstance(value, dict):
            return any(self._contains_nullish(item) for item in value.values())
        if isinstance(value, list):
            return any(self._contains_nullish(item) for item in value)
        return False

    def _contains_duplicate_strings(self, value: Any) -> bool:
        if isinstance(value, list):
            scalar_strings = [item.strip().lower() for item in value if isinstance(item, str) and item.strip()]
            if len(scalar_strings) != len(set(scalar_strings)):
                return True
            return any(self._contains_duplicate_strings(item) for item in value)
        if isinstance(value, dict):
            return any(self._contains_duplicate_strings(item) for item in value.values())
        return False
