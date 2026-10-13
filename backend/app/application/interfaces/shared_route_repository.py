from abc import ABC, abstractmethod

from app.application.schemas.route_schemas import (
    CreateSharedRouteRequest,
    SharedRouteDetailResponse,
    SharedRouteSummaryResponse,
)


class SharedRouteRepository(ABC):
    @abstractmethod
    def list_routes(self) -> list[SharedRouteSummaryResponse]:
        raise NotImplementedError

    @abstractmethod
    def list_route_details(self) -> list[SharedRouteDetailResponse]:
        raise NotImplementedError

    @abstractmethod
    def search_route_details(
        self,
        query: str,
        privacy_mode: str,
        page: int,
        page_size: int,
    ) -> tuple[list[SharedRouteDetailResponse], int]:
        raise NotImplementedError

    @abstractmethod
    def create_route(self, payload: CreateSharedRouteRequest) -> SharedRouteDetailResponse:
        raise NotImplementedError

    @abstractmethod
    def get_route(self, route_id: str) -> SharedRouteDetailResponse | None:
        raise NotImplementedError

    @abstractmethod
    def update_route(self, route_id: str, payload: CreateSharedRouteRequest) -> SharedRouteDetailResponse | None:
        raise NotImplementedError

    @abstractmethod
    def delete_route(self, route_id: str) -> bool:
        raise NotImplementedError
