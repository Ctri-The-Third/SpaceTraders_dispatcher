import pytest
import os
from behaviours.generic_behaviour import Behaviour
from straders_sdk.ship import Ship
from straders_sdk.models import Waypoint
from straders_sdk import SpaceTraders
import uuid

CLIENT_DETAILS_S = os.environ.get("ST_CLIENT_DETAILS", None)


def register_and_get_client() -> SpaceTraders:
    db_host = os.environ.get("ST_HOST_NAME", "localhost")
    db_port = os.environ.get("ST_DB_PORT", 5432)
    db_name = os.environ.get("ST_DB_NAME", "spacetraders")
    db_user = os.environ.get("ST_DB_USER", "spacetraders")
    db_pass = os.environ.get("ST_DB_PASSWORD", "spacetraders")

    st = SpaceTraders(
        db_host=db_host,
        db_port=db_port,
        db_name=db_name,
        db_user=db_user,
        db_pass=db_pass,
    )
    st.register("CTRI-TEST-" + str(uuid.uuid4())[0:4])
    return st


def test_ship_intrasolar():
    # test should take about 90 seconds
    st = register_and_get_client()

    resp = st.ships_view()  # should be a command ship
    assert resp
    assert isinstance(resp, dict)
    ship = resp[st.current_agent.symbol + "-1"]
    assert ship.role == "COMMAND"

    waypoints = st.waypoints_view(ship.nav.system_symbol)
    assert waypoints

    for waypoint in waypoints.values():
        waypoint: Waypoint
        if waypoint.symbol != ship.nav.waypoint_symbol:
            break
    bhv = Behaviour()
    bhv.st = st
    bhv.ship = ship

    assert ship.nav.waypoint_symbol != waypoint.symbol
    bhv.ship_intrasolar(waypoint)
    assert ship.nav.waypoint_symbol == waypoint.symbol

    pass


def test_ship_extract_till_full():
    # test should take about 10-15 minutes, pytest in the cloud might become expensive.
    st = register_and_get_client()

    resp = st.ships_view_one(st.current_agent.symbol + "-1")
    assert resp
    assert isinstance(resp, Ship)
    ship = resp
    assert ship.role == "COMMAND"

    bhv = Behaviour()
    bhv.st = st
    bhv.ship = ship

    mining_waypoint = st.find_waypoint_by_type(ship.nav.system_symbol, "ASTEROID_FIELD")
    bhv.ship_intrasolar(mining_waypoint)

    resp = st.ships_view_one(st.current_agent.symbol + "-1", True)
    assert resp
    assert isinstance(resp, Ship)
    ship = resp

    assert ship.nav.waypoint_symbol == mining_waypoint.symbol
    assert ship.nav.status == "IN_ORBIT"
    assert ship.cargo_units_used < ship.cargo_capacity

    bhv.extract_till_full()

    assert ship.cargo_units_used == ship.cargo_capacity
    pass
