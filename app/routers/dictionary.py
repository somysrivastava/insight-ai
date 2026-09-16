from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.dictionary import (
    ColumnMappingPatchRequest,
    ColumnMappingResponse,
    DictionaryBulkUpsertRequest,
    DictionarySuggestResponse,
)
from app.services import dictionary_service
from app.services.access_control import require_dataset_access
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/datasets", tags=["Data Dictionary"])


@router.get("/{dataset_id}/dictionary", response_model=list[ColumnMappingResponse])
def get_dictionary(dataset_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_dataset_access(db, dataset_id, current_user.id)
    return list(dictionary_service.get_dictionary(db, dataset_id).values())


@router.put("/{dataset_id}/dictionary", response_model=list[ColumnMappingResponse])
def bulk_upsert_dictionary(
    dataset_id: int,
    request: DictionaryBulkUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upserts only the columns given — a column not included here keeps whatever mapping it already had."""
    dataset = require_dataset_access(db, dataset_id, current_user.id)
    try:
        return [
            dictionary_service.upsert_mapping(
                db,
                dataset,
                column_name=item.column_name,
                display_name=item.display_name,
                description=item.description,
                unit=item.unit,
                is_metric=item.is_metric,
                is_dimension=item.is_dimension,
            )
            for item in request.mappings
        ]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{dataset_id}/dictionary/{column}", response_model=ColumnMappingResponse)
def update_dictionary_column(
    dataset_id: int,
    column: str,
    request: ColumnMappingPatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_dataset_access(db, dataset_id, current_user.id)
    mapping = dictionary_service.get_mapping(db, dataset_id, column)
    if not mapping:
        raise HTTPException(
            status_code=404,
            detail=f"No dictionary mapping exists yet for column '{column}' — use PUT to create one.",
        )
    return dictionary_service.update_mapping(db, mapping, **request.model_dump(exclude_unset=True))


@router.delete("/{dataset_id}/dictionary/{column}", status_code=204, response_class=Response)
def delete_dictionary_column(
    dataset_id: int, column: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    require_dataset_access(db, dataset_id, current_user.id)
    mapping = dictionary_service.get_mapping(db, dataset_id, column)
    if not mapping:
        raise HTTPException(status_code=404, detail=f"No dictionary mapping exists for column '{column}'.")
    dictionary_service.delete_mapping(db, mapping)
    return Response(status_code=204)


@router.post("/{dataset_id}/dictionary/suggest", response_model=DictionarySuggestResponse)
def suggest_dictionary(
    dataset_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Synchronous — one OpenAI call for every column that doesn't already
    have a saved mapping. Columns with an existing mapping are left
    untouched and reported back as skipped_existing.
    """
    dataset = require_dataset_access(db, dataset_id, current_user.id)
    try:
        saved, skipped = dictionary_service.auto_suggest(db, dataset)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset file not found in storage")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not generate dictionary suggestions: {str(e)}")
    return DictionarySuggestResponse(suggested=saved, skipped_existing=skipped)
