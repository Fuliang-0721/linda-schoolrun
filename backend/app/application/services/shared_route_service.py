from app.application.interfaces.shared_route_repository import SharedRouteRepository
from app.application.schemas.route_schemas import (
    CreateSharedRouteRequest,
    SharedRouteDetailResponse,
    SharedRouteSummaryResponse,
)
from app.core.exceptions import ResourceNotFoundError


class SharedRouteService:
    def __init__(self, repository: SharedRouteRepository):
        self._repository = repository

    def list_routes(self) -> list[SharedRouteSummaryResponse]:
        return self._repository.list_routes()

    def create_route(self, payload: CreateSharedRouteRequest) -> SharedRouteDetailResponse:
        return self._repository.create_route(payload)

    def get_route(self, route_id: str) -> SharedRouteDetailResponse:
        route = self._repository.get_route(route_id)
        if route is None:
            raise ResourceNotFoundError(f"Shared route '{route_id}' was not found.")
        return route
