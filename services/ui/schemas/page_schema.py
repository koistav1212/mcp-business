from pydantic import BaseModel, Field
from typing import Optional

class PageSchema(BaseModel):
    page_number: int = Field(default=1)
    page_type: str = Field(default="executive_company_snapshot")
    title: str
    executive_question: str
    executive_headline: str
    image_search_query: Optional[str] = None
