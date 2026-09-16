from app.services.export_service import (
    build_breakdown_document,
    build_insights_document,
    build_query_document,
    build_report_document,
    build_trends_document,
)


class TestBuildQueryDocument:
    def test_records_shape_becomes_table_rows(self):
        result = {"answer": "Revenue by region.", "data": {"operation": "groupby", "records": [{"region": "West", "revenue": 100}]}}
        doc = build_query_document("Query: sales.csv", result)
        assert doc["title"] == "Query: sales.csv"
        assert doc["answer"] == "Revenue by region."
        assert doc["table_rows"] == [{"region": "West", "revenue": 100}]
        assert doc["summary_fields"] is None
        assert doc["narrative"] is None
        assert doc["generated_at"]  # non-empty ISO timestamp

    def test_single_value_shape_becomes_summary_fields(self):
        result = {"answer": "Total revenue: 600.00.", "data": {"operation": "aggregate", "value": 600.0, "row_count": 6}}
        doc = build_query_document("Query: sales.csv", result)
        assert doc["table_rows"] is None
        assert doc["summary_fields"] == {"value": 600.0, "row_count": 6}
        # "operation" key is deliberately excluded from summary_fields
        assert "operation" not in doc["summary_fields"]

    def test_missing_data_key_handled_gracefully(self):
        doc = build_query_document("Query: sales.csv", {"answer": "No data."})
        assert doc["summary_fields"] == {}


class TestBuildInsightsDocument:
    def test_summary_stats_become_table_rows_with_column_name_merged_in(self):
        result = {
            "summary_stats": {"revenue": {"mean": 100.0, "max": 300.0}},
            "kpis": {"total_records": 6},
            "total_rows": 6,
            "total_columns": 5,
        }
        doc = build_insights_document("Insights: sales.csv", result)
        assert doc["table_rows"] == [{"column": "revenue", "mean": 100.0, "max": 300.0}]
        assert doc["summary_fields"]["total_records"] == 6
        assert doc["summary_fields"]["total_rows"] == 6
        assert doc["summary_fields"]["total_columns"] == 5

    def test_empty_summary_stats_yields_none_table_rows(self):
        doc = build_insights_document("Insights: sales.csv", {"summary_stats": {}, "kpis": {}})
        assert doc["table_rows"] is None


class TestBuildTrendsDocument:
    def test_trends_become_table_rows(self):
        result = {"trends": [{"month": "2024-01", "revenue": 100}], "date column": "order_date"}
        doc = build_trends_document("Trends: sales.csv", result)
        assert doc["table_rows"] == [{"month": "2024-01", "revenue": 100}]
        assert doc["summary_fields"] == {"date_column": "order_date"}

    def test_empty_trends_list_becomes_none(self):
        doc = build_trends_document("Trends: sales.csv", {"trends": []})
        assert doc["table_rows"] is None


class TestBuildBreakdownDocument:
    def test_breakdown_becomes_table_rows(self):
        result = {"breakdown": [{"region": "West", "revenue": 100}], "group_by": "region"}
        doc = build_breakdown_document("Breakdown by region: sales.csv", result)
        assert doc["table_rows"] == [{"region": "West", "revenue": 100}]
        assert doc["summary_fields"] == {"group_by": "region"}


class TestBuildReportDocument:
    def test_narrative_and_kpis_both_populated(self):
        result = {
            "kpis": {"total_records": 6, "total_value": 600.0},
            "executive_summary": {
                "headline": "Steady growth",
                "summary_points": ["Point A", "Point B"],
                "health_score": 82,
                "health_label": "Healthy",
                "recommendation": "Keep it up.",
            },
            "generated_at": "2024-06-01T00:00:00+00:00",
        }
        doc = build_report_document("Report: sales.csv", result)
        assert doc["table_rows"] is None
        assert doc["summary_fields"] == {"total_records": 6, "total_value": 600.0}
        assert doc["narrative"]["headline"] == "Steady growth"
        assert doc["narrative"]["summary_points"] == ["Point A", "Point B"]
        assert doc["narrative"]["health_score"] == 82
        assert doc["generated_at"] == "2024-06-01T00:00:00+00:00"

    def test_missing_executive_summary_defaults_narrative_fields_to_none(self):
        doc = build_report_document("Report: sales.csv", {"kpis": {}})
        assert doc["narrative"]["headline"] is None
        assert doc["narrative"]["summary_points"] == []
