from app.application.interfaces.shared_nfc_repository import SharedNfcRepository
from app.application.schemas.nfc_schemas import CreateSharedNfcRequest, SharedNfcResponse


class SharedNfcService:
    def __init__(self, repository: SharedNfcRepository):
        self._repository = repository

    def list_entries(self) -> list[SharedNfcResponse]:
        return self._repository.list_entries()

    def create_entry(self, payload: CreateSharedNfcRequest) -> SharedNfcResponse:
        return self._repository.create_entry(payload)
