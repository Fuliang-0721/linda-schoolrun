"""MySQL FLOAT loses coordinate precision, including in text protocol results.

Widen existing columns without changing row identity or order. Coordinates that
were already rounded must be restored separately from an authoritative source.
"""
from sqlalchemy import inspect, text
from sqlalchemy.dialects.mysql import FLOAT

COORDINATE_COLUMNS = {
    "shared_route_points": ("bd_longitude", "bd_latitude", "wgs_longitude", "wgs_latitude"),
    "client_telemetry": ("latitude", "longitude"),
}


def migrate_coordinate_precision(connection) -> None:
    if connection.dialect.name != "mysql":
        return
    inspector = inspect(connection)
    for table, names in COORDINATE_COLUMNS.items():
        if not inspector.has_table(table):
            continue
        changes = []
        for column in inspector.get_columns(table):
            if column["name"] in names and isinstance(column["type"], FLOAT):
                nullability = "NULL" if column["nullable"] else "NOT NULL"
                changes.append(f"MODIFY COLUMN `{column['name']}` DOUBLE {nullability}")
        if changes:
            connection.execute(text(f"ALTER TABLE `{table}` " + ", ".join(changes)))
