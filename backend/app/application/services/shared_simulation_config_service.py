from datetime import datetime, timezone

from app.application.schemas.simulation_config_schemas import (
    SaveSharedSimulationConfigRequest,
    SharedSimulationConfigResponse,
)
from app.application.schemas.auth_schemas import AccountResponse
from app.core.id_generator import generate_public_id
from app.core.exceptions import ResourceNotFoundError
from app.infrastructure.db.models.simulation_config import SharedSimulationConfigModel


class SharedSimulationConfigService:
    def __init__(self, db):
        self._db = db

    def list_configs(self, query: str = "") -> list[SharedSimulationConfigResponse]:
        statement = self._db.query(SharedSimulationConfigModel)
        normalized_query = (query or "").strip()
        if normalized_query:
            like_query = f"%{normalized_query}%"
            statement = statement.filter(SharedSimulationConfigModel.name.like(like_query))
        rows = statement.order_by(SharedSimulationConfigModel.updated_at.desc()).all()
        return [self._to_response(row) for row in rows]

    def create_config(
        self,
        payload: SaveSharedSimulationConfigRequest,
        account: AccountResponse | None = None,
    ) -> SharedSimulationConfigResponse:
        now = self._now_millis()
        row = SharedSimulationConfigModel(
            id=generate_public_id("simcfg"),
            name=payload.name.strip(),
            mode=(payload.mode or "speed").strip().lower(),
            speed=payload.speed,
            cadence=payload.cadence,
            loop_count=payload.loopCount,
            dynamic_intensity_enabled=payload.dynamicIntensityEnabled,
            intensity_variation_range=payload.intensityVariationRange,
            intensity_variation_frequency=payload.intensityVariationFrequency,
            natural_path_variation_enabled=payload.naturalPathVariationEnabled,
            path_variation_amplitude=payload.pathVariationAmplitude,
            natural_altitude_variation_enabled=payload.naturalAltitudeVariationEnabled,
            altitude_base_meters=payload.altitudeBaseMeters,
            altitude_variation_range=payload.altitudeVariationRange,
            altitude_variation_height_centimeters=payload.altitudeVariationHeightCentimeters,
            altitude_variation_probability=payload.altitudeVariationProbability,
            link_ratio_numerator=payload.linkRatioNumerator,
            steps_per_meter=payload.stepsPerMeter,
            author_name="" if account is None else account.username.strip(),
            uploader_tester=bool(account is not None),
            created_at=now,
            updated_at=now,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return self._to_response(row)

    def get_config(self, config_id: str) -> SharedSimulationConfigResponse:
        row = self._db.query(SharedSimulationConfigModel).filter(SharedSimulationConfigModel.id == config_id).first()
        if row is None:
            raise ResourceNotFoundError(f"Simulation config '{config_id}' was not found.")
        return self._to_response(row)

    def _to_response(self, row: SharedSimulationConfigModel) -> SharedSimulationConfigResponse:
        return SharedSimulationConfigResponse(
            id=row.id,
            name=row.name,
            mode=row.mode,
            speed=row.speed,
            cadence=row.cadence,
            loopCount=row.loop_count,
            dynamicIntensityEnabled=row.dynamic_intensity_enabled,
            intensityVariationRange=row.intensity_variation_range,
            intensityVariationFrequency=row.intensity_variation_frequency,
            naturalPathVariationEnabled=row.natural_path_variation_enabled,
            pathVariationAmplitude=row.path_variation_amplitude,
            naturalAltitudeVariationEnabled=row.natural_altitude_variation_enabled,
            altitudeBaseMeters=row.altitude_base_meters,
            altitudeVariationRange=row.altitude_variation_range,
            altitudeVariationHeightCentimeters=row.altitude_variation_height_centimeters,
            altitudeVariationProbability=row.altitude_variation_probability,
            linkRatioNumerator=row.link_ratio_numerator,
            stepsPerMeter=row.steps_per_meter,
            authorName=row.author_name or "",
            uploaderTester=row.uploader_tester,
            createdAt=row.created_at,
            updatedAt=row.updated_at,
        )

    def _now_millis(self) -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1000)
