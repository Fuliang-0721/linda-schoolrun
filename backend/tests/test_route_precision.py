import json
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from app.application.schemas.route_schemas import CreateSharedRouteRequest
from app.infrastructure.db.coordinate_precision import migrate_coordinate_precision
from app.infrastructure.db.models.route import SharedRouteModel, SharedRoutePointModel
from app.infrastructure.db.models.client_telemetry import ClientTelemetryModel
from app.infrastructure.repositories.shared_route_sql_repository import SharedRouteSqlRepository


def test_mysql_coordinate_columns_compile_as_double():
    ddl = str(CreateTable(SharedRoutePointModel.__table__).compile(dialect=mysql.dialect()))
    for name in ("bd_longitude", "bd_latitude", "wgs_longitude", "wgs_latitude"):
        assert f"{name} DOUBLE NOT NULL" in ddl
    telemetry_ddl = str(CreateTable(ClientTelemetryModel.__table__).compile(dialect=mysql.dialect()))
    assert "latitude DOUBLE" in telemetry_ddl and "longitude DOUBLE" in telemetry_ddl


def test_route_roundtrip_retains_shape_order_and_precision():
    engine = create_engine("sqlite://")
    SharedRouteModel.__table__.create(engine)
    SharedRoutePointModel.__table__.create(engine)
    # Values at the same scale as the affected routes: six-significant-digit
    # FLOAT text output collapsed these longitudes to 118.302.
    points = [
        dict(bdLongitude=118.30151067441716, bdLatitude=35.123000123456,
             wgsLongitude=118.289100123456, wgsLatitude=35.117000123456),
        dict(bdLongitude=118.30229594341398, bdLatitude=35.123700123456,
             wgsLongitude=118.289900123456, wgsLatitude=35.117700123456),
        dict(bdLongitude=118.30161067441716, bdLatitude=35.122300123456,
             wgsLongitude=118.289200123456, wgsLatitude=35.116300123456),
    ]
    with Session(engine) as db:
        repo = SharedRouteSqlRepository(db)
        created = repo.create_route(CreateSharedRouteRequest(name="precision-fixture", points=points))
        db.expire_all()
        result = json.loads(repo.get_route(created.id).model_dump_json())
        assert result["pointCount"] == 3
        for actual, expected in zip(result["points"], points):
            for name, value in expected.items():
                assert abs(actual[name] - value) < 1e-12
        assert len({p["bdLongitude"] for p in result["points"]}) == 3
    engine.dispose()


def test_migration_only_widens_existing_mysql_float_coordinates():
    connection = Mock()
    connection.dialect.name = "mysql"
    inspector = Mock()
    inspector.has_table.side_effect = lambda table: table == "shared_route_points"
    inspector.get_columns.return_value = [
        {"name": "bd_longitude", "type": mysql.FLOAT(), "nullable": False},
        {"name": "bd_latitude", "type": mysql.DOUBLE(), "nullable": False},
        {"name": "altitude", "type": mysql.FLOAT(), "nullable": False},
    ]
    with patch("app.infrastructure.db.coordinate_precision.inspect", return_value=inspector):
        migrate_coordinate_precision(connection)
    assert str(connection.execute.call_args.args[0]) == "ALTER TABLE `shared_route_points` MODIFY COLUMN `bd_longitude` DOUBLE NOT NULL"


def test_migration_is_noop_for_already_double_columns_and_sqlite():
    connection = Mock()
    connection.dialect.name = "mysql"
    inspector = Mock()
    inspector.has_table.return_value = True
    inspector.get_columns.return_value = [
        {"name": "bd_longitude", "type": mysql.DOUBLE(), "nullable": False},
        {"name": "latitude", "type": mysql.DOUBLE(), "nullable": True},
    ]
    with patch("app.infrastructure.db.coordinate_precision.inspect", return_value=inspector):
        migrate_coordinate_precision(connection)
        migrate_coordinate_precision(connection)
    connection.execute.assert_not_called()
    connection.dialect.name = "sqlite"
    migrate_coordinate_precision(connection)
    connection.execute.assert_not_called()
