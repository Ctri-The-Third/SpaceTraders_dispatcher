from ..models import Shipyard, ShipyardShip
import psycopg2
import logging


def _upsert_shipyard(connection, shipyard: Shipyard):
    try:
        sql = """INSERT INTO public.shipyard_types(
	shipyard_symbol, ship_type)
	VALUES (%s, %s)
    ON CONFLICT (shipyard_symbol, ship_type) DO NOTHING;"""
        for ship_type in shipyard.ship_types:
            connection.cursor().execute(sql, (shipyard.waypoint, ship_type))

        connection.commit()
    except Exception as err:
        logging.error(err)
