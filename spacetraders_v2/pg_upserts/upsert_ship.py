from ..ship import Ship
from ..models import Agent
import psycopg2
import logging

# from psycopg2 import connection


def _upsert_ship(connection, ship: Ship, owner: Agent = None):
    try:
        owner_name = ship.name.split("-")[0] if not owner else owner.symbol
        owner_faction = "" if not owner else owner.starting_faction
        sql = """INSERT into ship (ship_symbol, agent_name, faction_symbol, ship_role, cargo_capacity, cargo_in_use)
        values (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (ship_symbol) DO UPDATE
        SET agent_name = %s,
            faction_symbol = %s,
            ship_role = %s,
            cargo_capacity = %s,
            cargo_in_use = %s;"""
        cur = connection.cursor()

        cur.execute(
            sql,
            (
                ship.name,
                owner_name,
                owner_faction,
                ship.role,
                ship.cargo_capacity,
                ship.cargo_units_used,
                owner_name,
                owner_faction,
                ship.role,
                ship.cargo_capacity,
                ship.cargo_units_used,
            ),
        )

        sql = """INSERT into ship_nav
        (Ship_symbol, system_symbol, waypoint_symbol, departure_time, arrival_time, origin_waypoint, destination_waypoint, flight_status, flight_mode)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ship_symbol) DO UPDATE
        SET system_symbol = %s,
            waypoint_symbol = %s,
            departure_time = %s,
            arrival_time = %s,
            origin_waypoint = %s,
            destination_waypoint = %s,
            flight_status = %s,
            flight_mode = %s;"""
        cur = connection.cursor()
        cur.execute(
            sql,
            (
                ship.name,
                ship.nav.system_symbol,
                ship.nav.waypoint_symbol,
                ship.nav.departure_time,
                ship.nav.arrival_time,
                ship.nav.origin.symbol,
                ship.nav.destination.symbol,
                ship.nav.status,
                ship.nav.flight_mode,
                ship.nav.system_symbol,
                ship.nav.waypoint_symbol,
                ship.nav.departure_time,
                ship.nav.arrival_time,
                ship.nav.origin.symbol,
                ship.nav.destination.symbol,
                ship.nav.status,
                ship.nav.flight_mode,
            ),
        )

        connection.commit()
    except Exception as err:
        out_str = sql % (
            ship.name,
            ship.nav.system_symbol,
            ship.nav.waypoint_symbol,
            ship.nav.departure_time,
            ship.nav.arrival_time,
            ship.nav.origin.symbol,
            ship.nav.destination.symbol,
            ship.nav.status,
            ship.nav.flight_mode,
            ship.nav.system_symbol,
            ship.nav.waypoint_symbol,
            ship.nav.departure_time,
            ship.nav.arrival_time,
            ship.nav.origin.symbol,
            ship.nav.destination.symbol,
            ship.nav.status,
            ship.nav.flight_mode,
        )
        logging.error(err)
