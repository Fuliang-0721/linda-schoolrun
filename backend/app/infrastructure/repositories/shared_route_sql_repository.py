from datetime import datetime, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.application.interfaces.shared_route_repository import SharedRouteRepository
from app.application.schemas.route_schemas import (
    CreateSharedRouteRequest,
    RoutePointPayload,
    SharedRouteDetailResponse,
    SharedRouteSummaryResponse,
)
from app.core.id_generator import generate_public_id
from app.infrastructure.db.models.route import SharedRouteModel, SharedRoutePointModel


class SharedRouteSqlRepository(SharedRouteRepository):
    def __init__(self, db: Session):
        self._db = db

    def list_routes(self) -> list[SharedRouteSummaryResponse]:
        rows = (
            self._db.query(SharedRouteModel)
            .order_by(SharedRouteModel.created_at.desc())
            .all()
        )
        return [
            SharedRouteSummaryResponse(
                id=row.id,
                name=row.name,
                privacyMode=row.privacy_mode,
                pointCount=row.point_count,
                createdAt=row.created_at,
            )
            for row in rows
        ]

    def list_route_details(self) -> list[SharedRouteDetailResponse]:
        rows = (
            self._db.query(SharedRouteModel)
            .options(selectinload(SharedRouteModel.points))
            .order_by(SharedRouteModel.created_at.desc())
            .all()
        )
        return [self._to_detail_response(row) for row in rows]

    def search_route_details(
        self,
        query: str,
        privacy_mode: str,
        page: int,
        page_size: int,
    ) -> tuple[list[SharedRouteDetailResponse], int]:
        statement = self._db.query(SharedRouteModel).options(selectinload(SharedRouteModel.points))

        normalized_query = (query or "").strip()
        if normalized_query:
            like_query = f"%{normalized_query}%"
            statement = statement.filter(
                or_(
                    SharedRouteModel.id.like(like_query),
                    SharedRouteModel.name.like(like_query),
                )
            )

        if privacy_mode == "private":
            statement = statement.filter(SharedRouteModel.privacy_mode.is_(True))
        elif privacy_mode == "public":
            statement = statement.filter(SharedRouteModel.privacy_mode.is_(False))

        total = statement.with_entities(func.count(SharedRouteModel.id)).scalar() or 0
        rows = (
            statement
            .order_by(SharedRouteModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return [self._to_detail_response(row) for row in rows], total

    def create_route(self, payload: CreateSharedRouteRequest) -> SharedRouteDetailResponse:
        now = int(datetime.now(timezone.utc).timestamp() * 1000)
        route = SharedRouteModel(
            id=generate_public_id("route"),
            name=payload.name,
            privacy_mode=payload.privacyMode,
            point_count=len(payload.points),
            created_at=now,
            updated_at=now,
        )
        route.points = [
            SharedRoutePointModel(
                sort_order=index,
                bd_longitude=point.bdLongitude,
                bd_latitude=point.bdLatitude,
                wgs_longitude=point.wgsLongitude,
                wgs_latitude=point.wgsLatitude,
                altitude=point.altitude,
            )
            for index, point in enumerate(payload.points)
        ]
        self._db.add(route)
        self._db.commit()
        self._db.refresh(route)
        return self._to_detail_response(route)

    def get_route(self, route_id: str) -> SharedRouteDetailResponse | None:
        route = (
            self._db.query(SharedRouteModel)
            .options(selectinload(SharedRouteModel.points))
            .filter(SharedRouteModel.id == route_id)
            .first()
        )
        if route is None:
            return None
        return self._to_detail_response(route)

    def update_route(self, route_id: str, payload: CreateSharedRouteRequest) -> SharedRouteDetailResponse | None:
        route = (
            self._db.query(SharedRouteModel)
            .options(selectinload(SharedRouteModel.points))
            .filter(SharedRouteModel.id == route_id)
            .first()
        )
        if route is None:
            return None

        now = int(datetime.now(timezone.utc).timestamp() * 1000)
        route.name = payload.name
        route.privacy_mode = payload.privacyMode
        route.point_count = len(payload.points)
        route.updated_at = now
        route.points.clear()
        route.points.extend(
            [
                SharedRoutePointModel(
                    sort_order=index,
                    bd_longitude=point.bdLongitude,
                    bd_latitude=point.bdLatitude,
                    wgs_longitude=point.wgsLongitude,
                    wgs_latitude=point.wgsLatitude,
                    altitude=point.altitude,
                )
                for index, point in enumerate(payload.points)
            ]
        )
        self._db.commit()
        self._db.refresh(route)
        return self._to_detail_response(route)

    def delete_route(self, route_id: str) -> bool:
        route = self._db.query(SharedRouteModel).filter(SharedRouteModel.id == route_id).first()
        if route is None:
            return False
        self._db.delete(route)
        self._db.commit()
        return True

    def _to_detail_response(self, route: SharedRouteModel) -> SharedRouteDetailResponse:
        return SharedRouteDetailResponse(
            id=route.id,
            name=route.name,
            privacyMode=route.privacy_mode,
            pointCount=route.point_count,
            createdAt=route.created_at,
            points=[
                RoutePointPayload(
                    bdLongitude=point.bd_longitude,
                    bdLatitude=point.bd_latitude,
                    wgsLongitude=point.wgs_longitude,
                    wgsLatitude=point.wgs_latitude,
                    altitude=point.altitude,
                )
                for point in route.points
            ],
        )
