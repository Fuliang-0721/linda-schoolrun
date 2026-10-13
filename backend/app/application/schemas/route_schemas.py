from pydantic import BaseModel, Field, field_validator


class RoutePointPayload(BaseModel):
    bdLongitude: float
    bdLatitude: float
    wgsLongitude: float
    wgsLatitude: float
    altitude: float = 55.0


class CreateSharedRouteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    privacyMode: bool = False
    points: list[RoutePointPayload]

    @field_validator("points")
    @classmethod
    def validate_points(cls, points: list[RoutePointPayload]) -> list[RoutePointPayload]:
        if len(points) < 2:
            raise ValueError("Route requires at least 2 points.")
        return points


class SharedRouteSummaryResponse(BaseModel):
    id: str
    name: str
    privacyMode: bool
    pointCount: int
    createdAt: int


class SharedRouteDetailResponse(BaseModel):
    id: str
    name: str
    privacyMode: bool
    pointCount: int
    createdAt: int
    points: list[RoutePointPayload]


class SharedRouteListEnvelope(BaseModel):
    items: list[SharedRouteSummaryResponse]


class SharedRouteDetailEnvelope(BaseModel):
    data: SharedRouteDetailResponse


class SharedRouteAdminListEnvelope(BaseModel):
    page: int
    pageSize: int
    total: int
    totalPages: int
    items: list[SharedRouteDetailResponse]
