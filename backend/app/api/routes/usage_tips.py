from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.api.dependencies import get_db, get_optional_account, require_current_account
from app.application.schemas.auth_schemas import AccountResponse
from app.application.schemas.admin_schemas import ActionMessageResponse
from app.application.schemas.tip_schemas import (
    SaveUsageTipRequest,
    TipImportWordResponse,
    UsageTipEnvelope,
    UsageTipListEnvelope,
)
from app.application.services.usage_tip_service import UsageTipService
from app.core.exceptions import ResourceNotFoundError

router = APIRouter(prefix="/tips")


@router.get("", response_model=UsageTipListEnvelope)
def list_tips(
    q: str = "",
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    account: AccountResponse | None = Depends(get_optional_account),
    db=Depends(get_db),
) -> UsageTipListEnvelope:
    service = UsageTipService(db)
    items, total = service.list_tips(q, account, page, pageSize)
    total_pages = (total + pageSize - 1) // pageSize if total else 0
    return UsageTipListEnvelope(page=page, pageSize=pageSize, total=total, totalPages=total_pages, items=items)


@router.get("/{tip_id}", response_model=UsageTipEnvelope)
def get_tip(
    tip_id: str,
    account: AccountResponse | None = Depends(get_optional_account),
    db=Depends(get_db),
) -> UsageTipEnvelope:
    service = UsageTipService(db)
    try:
        tip = service.get_tip(tip_id, account)
    except ResourceNotFoundError as exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exception)) from exception
    return UsageTipEnvelope(data=tip)


@router.post("", response_model=UsageTipEnvelope, status_code=status.HTTP_201_CREATED)
def create_tip(
    payload: SaveUsageTipRequest,
    account: AccountResponse = Depends(require_current_account),
    db=Depends(get_db),
) -> UsageTipEnvelope:
    return UsageTipEnvelope(data=UsageTipService(db).create_tip(payload, account))


@router.put("/{tip_id}", response_model=UsageTipEnvelope)
def update_tip(
    tip_id: str,
    payload: SaveUsageTipRequest,
    account: AccountResponse = Depends(require_current_account),
    db=Depends(get_db),
) -> UsageTipEnvelope:
    service = UsageTipService(db)
    try:
        tip = service.update_tip(tip_id, payload, account)
    except ResourceNotFoundError as exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exception)) from exception
    return UsageTipEnvelope(data=tip)


@router.delete("/{tip_id}", response_model=ActionMessageResponse)
def delete_tip(
    tip_id: str,
    account: AccountResponse = Depends(require_current_account),
    db=Depends(get_db),
) -> ActionMessageResponse:
    service = UsageTipService(db)
    try:
        service.delete_tip(tip_id, account)
    except ResourceNotFoundError as exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exception)) from exception
    return ActionMessageResponse(message="使用技巧已删除")


@router.post("/import-word", response_model=TipImportWordResponse)
def import_word(
    file: UploadFile = File(...),
    _: AccountResponse = Depends(require_current_account),
    db=Depends(get_db),
) -> TipImportWordResponse:
    return UsageTipService(db).import_word(file)
