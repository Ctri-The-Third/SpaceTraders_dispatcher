from straders_sdk.client_api import SpaceTradersApiClient
from straders_sdk.client_interface import SpaceTradersClient
from straders_sdk.client_postgres import SpaceTradersPostgresClient
from straders_sdk.client_mediator import SpaceTradersMediatorClient
from straders_sdk.ship import Ship
from straders_sdk.models import Waypoint, WaypointTrait, Shipyard, Market, Agent
import pytest
import os
import json
from straders_sdk.models import Waypoint, WaypointTrait

# TODO: replace this with a method that creates a new one.

fallback_blob = {
    "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZGVudGlmaWVyIjoiTzJPIiwidmVyc2lvbiI6InYyIiwicmVzZXRfZGF0ZSI6IjIwMjMtMDctMjMiLCJpYXQiOjE2OTAzMDAyNTYsInN1YiI6ImFnZW50LXRva2VuIn0.CqoMTWIZlV-HpGxL1KKuUpKocICVfSQ-5mbF0a4hMN-WEM5tD-de1TTiuaZURvDPUkzdXNgpejFDuaukQbj6Lbjqm-TlijM2qk_YlC87iZwe5KgXDTwsI_oCaG8oe4dPl8dzo2l3J9kpT0wjBv2t2BJnCAn6-QzDQy4p4DYJmPwDv-XsiDwBEWiQsG7ogjdPQyKY92c46KQvF5O8WiB24eycBZkXBVNLJXTYPmeGKFEdzkUt9zmemCp9ABaWk_jF0o_VK-tQvnHBAlOXpq08-a0GYC4a16oVAOwujm7N6IzkpUQELv8gIMAWyLg8NPjUsh4pkdv2uJM7hVh-EO1oeg",
    "hq_sys": "X1-B13",
    "hq_wayp": "X1-B13-48027C",
    "market_wayp": "X1-B13-28060B",
    "shipyard_wayp": "X1-B13-48027C",
}
env_blob = os.environ.get("TEST_BLOB", None)
TEST_BLOB = json.loads(env_blob) if env_blob else fallback_blob


@pytest.fixture
def DB_INFO():
    return ()


def clients():
    token = TEST_BLOB["token"]
    return [
        # return ""
        SpaceTradersApiClient(token),
        SpaceTradersMediatorClient(
            token=token,
            db_host=os.environ.get("ST_HOST_NAME", "localhost"),
            db_port=os.environ.get("ST_DB_PORT", 5432),
            db_name=os.environ.get("ST_DB_NAME", "spacetraders"),
            db_user=os.environ.get("ST_DB_USER", "spacetraders"),
            db_pass=os.environ.get("ST_DB_PASSWORD", "spacetraders"),
            current_agent_symbol=Agent("", os.environ.get("ST_AGENT", "O2O"), ""),
        ),
        SpaceTradersPostgresClient(
            db_host=os.environ.get("ST_HOST_NAME", "localhost"),
            db_port=os.environ.get("ST_DB_PORT", 5432),
            db_name=os.environ.get("ST_DB_NAME", "spacetraders"),
            db_user=os.environ.get("ST_DB_USER", "spacetraders"),
            db_pass=os.environ.get("ST_DB_PASSWORD", "spacetraders"),
            current_agent_symbol=os.environ.get("ST_AGENT", "O2O"),
        ),
    ]


@pytest.mark.parametrize("st", clients())
def test_clients(st: SpaceTradersClient):
    assert isinstance(st, SpaceTradersClient)


@pytest.mark.parametrize("st", clients())
def test_waypoints_view(st: SpaceTradersClient):
    waypoints = st.waypoints_view(TEST_BLOB["hq_sys"])
    assert waypoints

    assert isinstance(waypoints, dict)
    assert len(waypoints) > 0
    for key, waypoint in waypoints.items():
        assert isinstance(key, str)
        assert isinstance(waypoint, Waypoint)


@pytest.mark.parametrize(
    "st",
    clients(),
)
def test_waypoints_view_one(st: SpaceTradersClient):
    waypoint = st.waypoints_view_one(TEST_BLOB["hq_sys"], TEST_BLOB["hq_wayp"])
    assert waypoint.symbol == TEST_BLOB["hq_wayp"]
    assert len(waypoint.traits) > 0
    assert isinstance(waypoint, Waypoint)


@pytest.mark.parametrize("st", clients())
def test_shipyard_info(st: SpaceTradersClient):
    wp = Waypoint(
        TEST_BLOB["hq_sys"], TEST_BLOB["shipyard_wayp"], "PLANET", 0, 0, [], [], {}, {}
    )
    wp.traits = [
        WaypointTrait("SHIPYARD", "Shipyard", "A place to buy and sell ships.")
    ]
    shipyard = st.system_shipyard(wp)
    assert isinstance(shipyard, Shipyard)
    assert len(shipyard.ship_types) > 0


@pytest.mark.parametrize("st", clients())
def test_market_info(st: SpaceTradersClient):
    wp = Waypoint(
        TEST_BLOB["hq_sys"], TEST_BLOB["market_wayp"], "PLANET", 0, 0, [], [], {}, {}
    )
    wp.traits = [
        WaypointTrait("MARKETPLACE", "Marketplace", "A place to buy and sell goods.")
    ]

    market = st.system_market(wp)
    assert isinstance(market, Market)


@pytest.mark.parametrize("st", clients())
def test_ships_view(st: SpaceTradersClient):
    ships = st.ships_view()
    assert isinstance(ships, dict)
    assert len(ships) > 0
    for key, ship in ships.items():
        assert isinstance(key, str)
        assert isinstance(ship, Ship)


if __name__ == "__MAIN__":
    connections = clients()
