from pydantic import BaseModel

class Workspace(BaseModel):
    query: str
    company: str | None = None
    workspace_type: str
    report_type: str
    depth: str
    required_data: list[str]
    required_visualizations: list[str]
    required_sources: list[str]
