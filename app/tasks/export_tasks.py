# WHY THIS FILE EXISTS:
# One Celery task per exportable thing (Day 15's convention). Each task
# re-runs the underlying computation fresh (calls ai_service/
# analytics_service/join_service/report_service directly, the same way
# the sync/async query endpoints already do) rather than trusting a
# client-supplied result blob, then hands the result to export_service
# for formatting. An ExportJob row is written once, when the task
# finishes — success or failure — never eagerly at submission; Celery's
# own result (via GET /jobs/{task_id}) already covers "is it ready."
#
# Each task has two try blocks: the outer one covers the access check
# (get_dataset_for_user / check_workspace_membership) — if that fails,
# there's no workspace to scope an audit row to, so it propagates as a
# plain Celery task failure. The inner one covers everything after
# access is confirmed, where workspace_id is always known, so a failure
# there gets a proper "failed" ExportJob row instead.

from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import ExportJob
from app.models.saved_join import SavedJoin
from app.services import export_service
from app.services.access_control import check_workspace_membership, get_dataset_for_user
from app.services.ai_service import answer_query, answer_query_for_df
from app.services.analytics_service import generate_breakdown, generate_insights, generate_trends
from app.services.join_service import execute_join, load_and_validate_datasets
from app.services.report_service import generate_full_report
from app.services.storage_service import get_storage_backend, get_storage_key, load_dataframe
from app.worker import celery_app

EXPORT_TTL_HOURS = 24

_EXTENSIONS = {"csv": "csv", "xlsx": "xlsx", "pdf": "pdf"}


def _save_export_job(db, *, workspace_id, user_id, source_type, source_id, params, format, status, file_path=None, error=None):
    export_job = ExportJob(
        workspace_id=workspace_id,
        user_id=user_id,
        source_type=source_type,
        source_id=source_id,
        params=params,
        format=format,
        status=status,
        file_path=file_path,
        error=error,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=EXPORT_TTL_HOURS),
    )
    db.add(export_job)
    db.commit()
    db.refresh(export_job)
    return export_job


def _write_export_file(workspace_id: int, source_type: str, source_id: int, format: str, file_bytes: bytes) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    filename = f"{source_type}_{source_id}_{timestamp}.{_EXTENSIONS[format]}"
    storage_key = get_storage_key(workspace_id, filename)
    get_storage_backend("exports").save(file_bytes, storage_key)
    return storage_key


def _export_result(export_job: ExportJob) -> dict:
    return {
        "export_id": export_job.id,
        "status": export_job.status,
        "format": export_job.format,
        "download_url": f"/exports/{export_job.id}" if export_job.status == "success" else None,
        "expires_at": export_job.expires_at.isoformat(),
        "error": export_job.error,
    }


@celery_app.task(name="export_tasks.export_dataset")
def export_dataset_task(dataset_id: int, user_id: int, source: str, format: str, question: str | None, group_by: str | None) -> dict:
    db = SessionLocal()
    params = {"source": source, "question": question, "group_by": group_by}
    source_type = "dataset_" + source
    try:
        dataset = get_dataset_for_user(db, dataset_id, user_id)

        try:
            if source == "query":
                result = answer_query(dataset, question)
                doc = export_service.build_query_document(f"Query: {dataset.filename}", result)
            elif source == "insights":
                result = generate_insights(dataset.file_path)
                doc = export_service.build_insights_document(f"Insights: {dataset.filename}", result)
            elif source == "trends":
                result = generate_trends(dataset.file_path)
                doc = export_service.build_trends_document(f"Trends: {dataset.filename}", result)
            elif source == "breakdown":
                result = generate_breakdown(dataset.file_path, group_by)
                doc = export_service.build_breakdown_document(f"Breakdown by {group_by}: {dataset.filename}", result)
            else:
                raise ValueError(f"Unsupported export source: {source}")

            file_bytes = export_service.render(doc, format)
            file_path = _write_export_file(dataset.workspace_id, source_type, dataset_id, format, file_bytes)
        except Exception as e:
            export_job = _save_export_job(
                db, workspace_id=dataset.workspace_id, user_id=user_id, source_type=source_type,
                source_id=dataset_id, params=params, format=format, status="failed", error=str(e),
            )
            return _export_result(export_job)

        export_job = _save_export_job(
            db, workspace_id=dataset.workspace_id, user_id=user_id, source_type=source_type,
            source_id=dataset_id, params=params, format=format, status="success", file_path=file_path,
        )
        return _export_result(export_job)
    finally:
        db.close()


@celery_app.task(name="export_tasks.export_join_query")
def export_join_query_task(join_id: int, user_id: int, question: str, format: str) -> dict:
    db = SessionLocal()
    params = {"question": question}
    try:
        saved_join = db.query(SavedJoin).filter(SavedJoin.id == join_id).first()
        if not saved_join:
            raise ValueError(f"Saved join {join_id} not found.")
        check_workspace_membership(db, saved_join.workspace_id, user_id)

        try:
            dataframes, _ = load_and_validate_datasets(db, user_id, saved_join.datasets)
            joined_df = execute_join(dataframes, saved_join.joins)
            result = answer_query_for_df(joined_df, question)
            doc = export_service.build_query_document(f"Join query: {saved_join.name}", result)

            file_bytes = export_service.render(doc, format)
            file_path = _write_export_file(saved_join.workspace_id, "join_query", join_id, format, file_bytes)
        except Exception as e:
            export_job = _save_export_job(
                db, workspace_id=saved_join.workspace_id, user_id=user_id, source_type="join_query",
                source_id=join_id, params=params, format=format, status="failed", error=str(e),
            )
            return _export_result(export_job)

        export_job = _save_export_job(
            db, workspace_id=saved_join.workspace_id, user_id=user_id, source_type="join_query",
            source_id=join_id, params=params, format=format, status="success", file_path=file_path,
        )
        return _export_result(export_job)
    finally:
        db.close()


@celery_app.task(name="export_tasks.export_report")
def export_report_task(dataset_id: int, user_id: int, format: str) -> dict:
    db = SessionLocal()
    params: dict = {}
    try:
        dataset = get_dataset_for_user(db, dataset_id, user_id)

        try:
            df = load_dataframe(dataset.file_path)
            report = generate_full_report(dataset.id, dataset.filename, df)
            doc = export_service.build_report_document(f"Full Report: {dataset.filename}", report.model_dump())

            file_bytes = export_service.render(doc, format, is_report=True)
            file_path = _write_export_file(dataset.workspace_id, "report", dataset_id, format, file_bytes)
        except Exception as e:
            export_job = _save_export_job(
                db, workspace_id=dataset.workspace_id, user_id=user_id, source_type="report",
                source_id=dataset_id, params=params, format=format, status="failed", error=str(e),
            )
            return _export_result(export_job)

        export_job = _save_export_job(
            db, workspace_id=dataset.workspace_id, user_id=user_id, source_type="report",
            source_id=dataset_id, params=params, format=format, status="success", file_path=file_path,
        )
        return _export_result(export_job)
    finally:
        db.close()
