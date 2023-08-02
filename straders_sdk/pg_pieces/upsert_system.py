import psycopg2


from ..models import System
from ..pg_upserts.upsert_waypoint import _upsert_waypoint


def _upsert_system(connection, system: System):
    try:
        sql = """INSERT INTO systems (symbol, type, sector_symbol, x, y)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (symbol) DO UPDATE
                    SET type = %s,  sector_symbol = %s, x = %s, y = %s"""
        connection.cursor().execute(
            sql,
            (
                system.symbol,
                system.system_type,
                system.sector_symbol,
                system.x,
                system.y,
                system.system_type,
                system.sector_symbol,
                system.x,
                system.y,
            ),
        )
        connection.commit()

    except Exception as err:
        print(err)

    for waypoint in system.waypoints:
        _upsert_waypoint(connection, waypoint)
