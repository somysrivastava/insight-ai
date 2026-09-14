from app.database import SessionLocal
from app.models.saved_join import SavedJoin
from app.services import ai_service, join_service
from app.worker import celery_app


def _save_join_if_named(db, workspace_id: int, user_id: int, name, datasets, joins) -> "int | None":
    if not name:
        return None
    existing = db.query(SavedJoin).filter(SavedJoin.workspace_id == workspace_id, SavedJoin.name == name).first()
    if existing:
        raise ValueError(f"A saved join named '{name}' already exists in this workspace.")
    saved = SavedJoin(workspace_id=workspace_id, user_id=user_id, name=name, datasets=datasets, joins=joins)
    db.add(saved)
    db.commit()
    db.refresh(saved)
    return saved.id


@celery_app.task(name="join_tasks.run_join_query")
def run_join_query_task(datasets: list, joins: list, question: str, user_id: int, name=None) -> dict:
    """
    Async version of POST /joins — re-validates access to every dataset
    independently (join_service.load_and_validate_datasets), same
    defense-in-depth reasoning as every other task in app/tasks/.
    """
    db = SessionLocal()
    try:
        dataframes, workspace_id = join_service.load_and_validate_datasets(db, user_id, datasets)
        joined_df = join_service.execute_join(dataframes, joins)
        join_id = _save_join_if_named(db, workspace_id, user_id, name, datasets, joins)
        result = ai_service.answer_query_for_df(joined_df, question)
        result["join_id"] = join_id
        return result
    finally:
        db.close()


@celery_app.task(name="join_tasks.run_saved_join_query")
def run_saved_join_query_task(join_id: int, question: str, user_id: int) -> dict:
    """Async version of POST /joins/{id}/query."""
    db = SessionLocal()
    try:
        saved = db.query(SavedJoin).filter(SavedJoin.id == join_id).first()
        if not saved:
            raise ValueError(f"Saved join {join_id} not found.")

        dataframes, _ = join_service.load_and_validate_datasets(db, user_id, saved.datasets)
        joined_df = join_service.execute_join(dataframes, saved.joins)
        result = ai_service.answer_query_for_df(joined_df, question)
        result["join_id"] = saved.id
        return result
    finally:
        db.close()
