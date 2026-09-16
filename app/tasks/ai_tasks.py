from app.database import SessionLocal
from app.services import ai_service
from app.tasks.common import load_owned_dataset
from app.worker import celery_app


@celery_app.task(name="ai_tasks.run_query")
def run_query_task(dataset_id: int, user_id: int, question: str) -> dict:
    db = SessionLocal()
    try:
        dataset = load_owned_dataset(db, dataset_id, user_id)
        return ai_service.answer_query(dataset, question, db)
    finally:
        db.close()
