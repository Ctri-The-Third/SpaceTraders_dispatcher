from spacetraders_v2.client_api import SpaceTradersApiClient
from spacetraders_v2.client_interface import SpaceTradersClient
from spacetraders_v2.client_postgres import SpaceTradersPostgresClient
from spacetraders_v2.client_mediator import SpaceTradersMediatorClient
from spacetraders_v2.ship import Ship
import pytest
import os

from spacetraders_v2.models import Waypoint, WaypointTrait

# TODO: replace this with a method that creates a new one.

HEADQUARTERS_WAYPOINT = "X1-MP2-12220Z"

SAMPLE_SHIP_JSON = {
    "data": {
        "symbol": "string",
        "registration": {
            "name": "string",
            "factionSymbol": "string",
            "role": "FABRICATOR",
        },
        "nav": {
            "systemSymbol": "string",
            "waypointSymbol": "string",
            "route": {
                "destination": {
                    "symbol": "string",
                    "type": "PLANET",
                    "systemSymbol": "string",
                    "x": 0,
                    "y": 0,
                },
                "departure": {
                    "symbol": "string",
                    "type": "PLANET",
                    "systemSymbol": "string",
                    "x": 0,
                    "y": 0,
                },
                "departureTime": "2019-08-24T14:15:22Z",
                "arrival": "2019-08-24T14:15:22Z",
            },
            "status": "IN_TRANSIT",
            "flightMode": "CRUISE",
        },
        "crew": {
            "current": 0,
            "required": 0,
            "capacity": 0,
            "rotation": "STRICT",
            "morale": 0,
            "wages": 0,
        },
        "frame": {
            "symbol": "FRAME_PROBE",
            "name": "string",
            "description": "string",
            "condition": 0,
            "moduleSlots": 0,
            "mountingPoints": 0,
            "fuelCapacity": 0,
            "requirements": {"power": 0, "crew": 0, "slots": 0},
        },
        "reactor": {
            "symbol": "REACTOR_SOLAR_I",
            "name": "string",
            "description": "string",
            "condition": 0,
            "powerOutput": 1,
            "requirements": {"power": 0, "crew": 0, "slots": 0},
        },
        "engine": {
            "symbol": "ENGINE_IMPULSE_DRIVE_I",
            "name": "string",
            "description": "string",
            "condition": 0,
            "speed": 1,
            "requirements": {"power": 0, "crew": 0, "slots": 0},
        },
        "modules": [
            {
                "symbol": "MODULE_MINERAL_PROCESSOR_I",
                "capacity": 0,
                "range": 0,
                "name": "string",
                "description": "string",
                "requirements": {"power": 0, "crew": 0, "slots": 0},
            }
        ],
        "mounts": [
            {
                "symbol": "MOUNT_GAS_SIPHON_I",
                "name": "string",
                "description": "string",
                "strength": 0,
                "deposits": ["QUARTZ_SAND"],
                "requirements": {"power": 0, "crew": 0, "slots": 0},
            }
        ],
        "cargo": {
            "capacity": 0,
            "units": 0,
            "inventory": [
                {
                    "symbol": "string",
                    "name": "string",
                    "description": "string",
                    "units": 1,
                }
            ],
        },
        "fuel": {
            "current": 0,
            "capacity": 0,
            "consumed": {"amount": 0, "timestamp": "2019-08-24T14:15:22Z"},
        },
    }
}


@pytest.fixture
def DB_INFO():
    return ()


@pytest.fixture
def STARTING_SYSTEM():
    return "X1-MP2"


def clients():
    token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZGVudGlmaWVyIjoiTzJPIiwidmVyc2lvbiI6InYyIiwicmVzZXRfZGF0ZSI6IjIwMjMtMDctMDgiLCJpYXQiOjE2ODkzMzg3MTQsInN1YiI6ImFnZW50LXRva2VuIn0.rjivh2lXRB3el7ghQOhfjUV1KLb9saqe8QnBgL8lLMWV1CWQpRerB6fx2oaYlt4tAxPJf81RSGtzMY5keGRwKmL-82HiP3WwM3JRtffbtXwneV3PjyDOVrz1bwMCAFQ4Ahln73AzHXRW_uiPcRIXvE4XlRn1N19dS_HIKQkbAr6kiQzvcDzJMhlgFMCKOaSAZ0_ht8-T_Ha-m6NtlqIrrlLgoAxDXyz3E1l5Yuw5_ZX_FP8WcJ3ndlV4FNlZbUvikUiEJ7n77wmG0QTLajbbe1hydYjTDBF1bKISRvdbxVAEslxvNW2NqwlaLaoyZaRjjooOx-gifTb288G6JYGqQw"
    return [
        # return ""
        SpaceTradersApiClient(token),
        SpaceTradersPostgresClient(
            token,
            db_host=os.environ.get("ST_HOST_NAME", "localhost"),
            db_name=os.environ.get("ST_DB_NAME", "spacetraders"),
            db_user=os.environ.get("ST_DB_USER", "spacetraders"),
            db_pass=os.environ.get("ST_DB_PASSWORD", "spacetraders"),
        ),
        SpaceTradersMediatorClient(
            token=token,
            db_host=os.environ.get("ST_HOST_NAME", "localhost"),
            db_name=os.environ.get("ST_DB_NAME", "spacetraders"),
            db_user=os.environ.get("ST_DB_USER", "spacetraders"),
            db_pass=os.environ.get("ST_DB_PASSWORD", "spacetraders"),
        ),
    ]


@pytest.mark.parametrize("st", clients())
def test_clients(st: SpaceTradersClient):
    assert isinstance(st, SpaceTradersClient)


@pytest.mark.parametrize("st", clients())
def test_waypoints_view(st: SpaceTradersClient, STARTING_SYSTEM):
    waypoints = st.waypoints_view(STARTING_SYSTEM)
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
def test_waypoints_view_one(st: SpaceTradersClient, STARTING_SYSTEM):
    waypoint = st.waypoints_view_one(STARTING_SYSTEM, HEADQUARTERS_WAYPOINT)
    assert waypoint.symbol == HEADQUARTERS_WAYPOINT
    assert waypoint.type == "PLANET"
    assert waypoint.x == 7
    assert waypoint.y == 25
    assert len(waypoint.traits) == 5
    assert isinstance(waypoint, Waypoint)


@pytest.mark.parametrize(
    "st",
    clients(),
)
def test_shipyard_info(st: SpaceTradersClient):
    wp = Waypoint("", "TEST", "PLANET", 0, 0, [])
    wp.traits = [
        WaypointTrait("SHIPYARD", "Shipyard", "A place to buy and sell ships.")
    ]
    types = st.system_shipyard_ships(wp)
