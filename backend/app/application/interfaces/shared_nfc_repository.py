from abc import ABC, abstractmethod

from app.application.schemas.nfc_schemas import CreateSharedNfcRequest, SharedNfcResponse


class SharedNfcRepository(ABC):
    @abstractmethod
    def list_entries(self) -> list[SharedNfcResponse]:
        raise NotImplementedError

    @abstractmethod
    def create_entry(self, payload: CreateSharedNfcRequest) -> SharedNfcResponse:
        raise NotImplementedError

    @abstractmethod
    def search_entries(
        self,
        query: str,
        page: int,
        page_size: int,
    ) -> tuple[list[SharedNfcResponse], int]:
        raise NotImplementedError

    @abstractmethod
    def update_entry(self, entry_id: str, payload: CreateSharedNfcRequest) -> SharedNfcResponse | None:
        raise NotImplementedError

    @abstractmethod
    def delete_entry(self, entry_id: str) -> bool:
        raise NotImplementedError
