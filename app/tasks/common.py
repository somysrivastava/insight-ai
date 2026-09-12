from sqlalchemy.orm import Session

from app.models import Dataset


def load_owned_dataset(db: Session, dataset_id: int, user_id: int) -> Dataset:
    """
    Loads a Dataset row and verifies ownership, for use inside Celery tasks.

    Tasks run in a separate process from the HTTP request that submitted
    them, so this re-validates ownership independently rather than trusting
    that the submitting endpoint's own check still holds by the time the
    task actually executes — the same defense-in-depth reasoning as never
    trusting a model's column claims without checking them against the
    real data (see ai_service.py / Day 14).
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise ValueError(f"Dataset {dataset_id} not found.")
    if dataset.user_id != user_id:
        raise PermissionError("Access denied.")
    return dataset
