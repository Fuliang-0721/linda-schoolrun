from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_nfc_service
from app.application.schemas.nfc_schemas import (
    CreateSharedNfcRequest,
    SharedNfcEnvelope,
    SharedNfcListEnvelope,
)
from app.application.services.shared_nfc_service import SharedNfcService
from app.web.auth import require_admin_session

router = APIRouter()


@router.get("", response_model=SharedNfcListEnvelope)
def list_shared_nfc(
    nfc_service: SharedNfcService = Depends(get_nfc_service),
) -> SharedNfcListEnvelope:
    return SharedNfcListEnvelope(items=nfc_service.list_entries())


@router.post("", response_model=SharedNfcEnvelope, status_code=status.HTTP_201_CREATED)
def create_shared_nfc(
    payload: CreateSharedNfcRequest,
    _admin=Depends(require_admin_session),
    nfc_service: SharedNfcService = Depends(get_nfc_service),
) -> SharedNfcEnvelope:
    return SharedNfcEnvelope(data=nfc_service.create_entry(payload))
