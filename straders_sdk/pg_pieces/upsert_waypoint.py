import psycopg2


from ..models import Waypoint, WaypointTrait


def _upsert_waypoint(connection, waypoint: Waypoint):
    try:
        sql = """INSERT INTO waypoints (symbol, type, system_symbol, x, y, checked)
                VALUES (%s, %s, %s, %s, %s, True)
                ON CONFLICT (symbol) DO UPDATE
                    SET 
                    type = EXCLUDED.type
                , system_symbol = EXCLUDED.system_symbol
                , x = EXCLUDED.x, y = EXCLUDED.y
                , checked = EXCLUDED.checked"""
        connection.cursor().execute(
            sql,
            (
                waypoint.symbol,
                waypoint.type,
                waypoint.system_symbol,
                waypoint.x,
                waypoint.y,
            ),
        )

        for trait in waypoint.traits:
            sql = """INSERT INTO waypoint_traits (waypoint, symbol, name, description)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (waypoint, symbol) DO UPDATE
                        SET name = EXCLUDED.name, description = EXCLUDED.description"""
            connection.cursor().execute(
                sql,
                (
                    waypoint.symbol,
                    trait.symbol,
                    trait.name,
                    trait.description,
                ),
            )
        connection.commit()
    except Exception as err:
        print(err)
        connection.rollback()
