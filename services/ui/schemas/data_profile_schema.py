from typing import Any, Dict, List
from pydantic import BaseModel, Field

class DataProfile(BaseModel):
    financial: bool = False
    news: bool = False
    risk: bool = False
    social: bool = False
    technology: bool = False
    competition: bool = False
    leadership: bool = False
    patents: bool = False
    macro: bool = False
    sec: bool = False
    knowledge_graph: bool = False
