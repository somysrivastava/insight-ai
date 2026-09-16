from app.database import SessionLocal
from app.services import analytics_service
from app.tasks.common import load_owned_dataset
from app.worker import celery_app


@celery_app.task(name="analytics_tasks.generate_insights")
def generate_insights_task(dataset_id: int, user_id: int) -> dict:
    db = SessionLocal()
    try:
        dataset = load_owned_dataset(db, dataset_id, user_id)
        result = analytics_service.get_cached_insights(dataset_id, dataset.file_path)
        return {"dataset_id": dataset_id, "dataset_name": dataset.filename, **result}
    finally:
        db.close()


@celery_app.task(name="analytics_tasks.generate_trends")
def generate_trends_task(dataset_id: int, user_id: int) -> dict:
    db = SessionLocal()
    try:
        dataset = load_owned_dataset(db, dataset_id, user_id)
        result = analytics_service.get_cached_trends(dataset_id, dataset.file_path)
        return {"dataset_id": dataset_id, "dataset_name": dataset.filename, **result}
    finally:
        db.close()


@celery_app.task(name="analytics_tasks.generate_breakdown")
def generate_breakdown_task(dataset_id: int, user_id: int, group_by: str) -> dict:
    db = SessionLocal()
    try:
        dataset = load_owned_dataset(db, dataset_id, user_id)
        result = analytics_service.get_cached_breakdown(dataset_id, dataset.file_path, group_by)
        return {"dataset_id": dataset_id, "dataset_name": dataset.filename, **result}
    finally:
        db.close()
