from enum import Enum
from mailbox import linesep
from typing import Optional

from numpy._core.strings import title
from pydantic import BaseModel, Field


class ChartType(str, Enum):
    bar = "bar"  # we are using enums for supported chart tpes because it prevents invalid chart types strings to reach the service layer
    line = "line"
    pie = "pie"
    scatter = "scatter"


class BarChartRequest(BaseModel):
    category_column: str = Field(
        ..., description="column to use as X-axis eg 'product_name'"
    )
    value_column: str = Field(..., description="column to use as Y-axis eg 'revenue'")
    top_n: int = Field(
        default=10,
        ge=1,
        le=50,
        description="show top N categories by value. Default 10",
    )
    title: Optional[str] = Field(
        default=None, description="Chart title, Auto-generated if not provided"
    )


class LineChartRequest(BaseModel):
    date_column: str = Field(..., description="column containing date values eg 'date'")
    value_column: str = Field(..., description="column to use as Y-axis eg 'sales'")
    group_by: Optional[str] = Field(
        default=None,
        description="Optional column to split into multiple lines (e.g. region)'",
    )
    title: Optional[str] = None


class PieChartRequest(BaseModel):
    category_column: str = Field(..., description="column to use as X-axis eg 'product_name'")
    value_column: str = Field(..., description="column to use as Y-axis eg 'revenue'")
    top_n: int = Field(
        default=10,
        ge=1,
        le=50,
        description="show top N categories by value. Default 10",
    )
    title: Optional[str] = Field(
        default=None, description="Chart title, Auto-generated if not provided"
    )


class ScatterChartRequest(BaseModel):
    x_column: str = Field(..., description="column to use as X-axis eg 'product_name'")
    y_column: str = Field(..., description="column to use as Y-axis eg 'revenue'")
    color_column: Optional[str] = Field(
        default=None,
        description="Optional column to use as color (e.g. region)",
    )
    title: Optional[str] = None


class DashboardRequest(BaseModel):
    category_column: str = Field(..., description="column to use as category eg 'product_name'")
    value_column: str = Field(..., description="column to use as value eg 'revenue'")
    date_column: Optional[str] =None
    top_n: int = Field(default=8, ge=2, le=20)
    title: Optional[str] = Field(
        default="InsightAI executive dashboard",
    )

class ChartResponse(BaseModel):
    chart_json: str
    chart_type: str
    columns_used: dict
    row_count: int
    
