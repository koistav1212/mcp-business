from pydantic import BaseModel, Field
from typing import List, Optional
from .page_schema import PageSchema
from .component_schema import ComponentSchema

class ExecutiveTakeaway(BaseModel):
    text: str
    evidence_paths: List[str] = Field(default_factory=list)

class UIValidation(BaseModel):
    component_count: int
    duplicate_components: List[str] = Field(default_factory=list)
    null_values_rendered: bool = False
    raw_duplicate_products_rendered: bool = False
    biography_style_detected: bool = False
    all_claims_traceable: bool = True
    passed: bool = True

class PageData(BaseModel):
    page: PageSchema
    components: List[ComponentSchema]

class UISchema(BaseModel):
    pages: List[PageData] = Field(default_factory=list)
    executive_takeaway: ExecutiveTakeaway
    validation: Optional[UIValidation] = None
