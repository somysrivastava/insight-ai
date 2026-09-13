from sqlalchemy.orm import Session

from app.models import Dataset
from app.services.access_control import get_dataset_for_user


def load_owned_dataset(db: Session, dataset_id: int, user_id: int) -> Dataset:
    """
    Loads a Dataset row and verifies the user has access to it, for use
    inside Celery tasks.

    Tasks run in a separate process from the HTTP request that submitted
    them, so this re-validates access independently rather than trusting
    that the submitting endpoint's own check still holds by the time the
    task actually executes — the same defense-in-depth reasoning as never
    trusting a model's column claims without checking them against the
    real data (see ai_service.py / Day 14).

    Delegates to the same access_control.get_dataset_for_user() every
    router uses (Day 16) — one definition of "can this user see this
    dataset," not a second copy that can drift from the router version.
    """
    return get_dataset_for_user(db, dataset_id, user_id)
