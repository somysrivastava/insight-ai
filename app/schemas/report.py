from numpy._core.multiarray import interp_complex
from pydantic import BaseModel
from typing import Any, Optional

from sqlalchemy.engine.interfaces import ReflectedComputed

class KPIReport(BaseModel):
    dataset_id: int
    filename: str
    kpis: dict[str, Any]

class ExecutiveSummary(BaseModel):
    dataset_id: int
    filename: str
    headline: str
    summary_points: list[str]
    health_score: float
    health_label: str
    recommendation: str

class FullReport(BaseModel):
    dataset_id: int
    filename: str
    kpis: dict[str, Any]
    executive_summary: ExecutiveSummary
    chart_endpoints: dict[str, str]
    generated_at: str
