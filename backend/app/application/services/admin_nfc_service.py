from app.application.interfaces.shared_nfc_repository import SharedNfcRepository
from app.application.schemas.nfc_schemas import CreateSharedNfcRequest, SharedNfcResponse
from app.core.exceptions import ResourceNotFoundError


class AdminNfcService:
    def __init__(self, repository: SharedNfcRepository):
        self._repository = repository

    def list_entries(self) -> list[SharedNfcResponse]:
        return self._repository.list_entries()

    def search_entries(
        self,
        query: str,
        page: int,
        page_size: int,
    ) -> tuple[list[SharedNfcResponse], int]:
        return self._repository.search_entries(query, page, page_size)

    def update_entry(self, entry_id: str, payload: CreateSharedNfcRequest) -> SharedNfcResponse:
        entry = self._repository.update_entry(entry_id, payload)
        if entry is None:
            raise ResourceNotFoundError(f"Shared NFC '{entry_id}' was not found.")
        return entry

    def delete_entry(self, entry_id: str) -> None:
        deleted = self._repository.delete_entry(entry_id)
        if not deleted:
            raise ResourceNotFoundError(f"Shared NFC '{entry_id}' was not found.")
