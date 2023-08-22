import sys
import json
import psycopg2, psycopg2.sql
from straders_sdk.client_mediator import SpaceTradersMediatorClient as SpaceTraders
from straders_sdk.ship import Ship
from straders_sdk.contracts import Contract
from straders_sdk.models import ShipyardShip, Waypoint, Shipyard, Survey, System
from straders_sdk.local_response import LocalSpaceTradersRespose
from straders_sdk.utils import (
    set_logging,
    waypoint_slicer,
    try_execute_select,
    try_execute_upsert,
)
import logging
from dispatcherWK7 import BHVR_EXPLORE_SYSTEM


RECON_AGENTS_MAX = 1
logger = logging.getLogger(__name__)


class ReconConductor:

    """This class will manage the recon agents and their behaviour. Expects"""

    def __init__(
        self, user: dict, max_agents: int = RECON_AGENTS_MAX, recon_prefix: str = "ZTRI"
    ) -> None:
        client = self.client = SpaceTraders(
            "",
            db_host=user["db_host"],
            db_port=user["db_port"],
            db_name=user["db_name"],
            db_user=user["db_user"],
            db_pass=user["db_pass"],
        )
        self.connection = client.db_client.connection
        agent_regex = f"{recon_prefix}.*"

        agents = [
            agent
            for agent in user.get("agents", [])
            if agent_regex.match(agent["username"])
        ]
        if len(agents) < max_agents:
            for i in range(len(agents) + 1, max_agents + 1):
                agent_name = f"{recon_prefix}-{i}-"
                token = register_and_store_user(agent_name)
                agents.append({"username": agent_name, "token": token})


def register_and_store_user(username) -> str:
    "returns the token"
    try:
        user = json.load(open("user.json", "r"))
    except FileNotFoundError:
        json.dump(
            {"email": "", "faction": "COSMIC", "agents": []},
            open("user.json", "w"),
            indent=2,
        )
        return
    logging.info("Starting up empty ST class to register user - expect warnings")
    st = SpaceTraders()
    resp = st.register(username, faction=user["faction"], email=user["email"])
    if not resp:
        # Log an error message with detailed information about the failed claim attempt
        logger.error(
            "Could not claim username %s, %d %s \n error code: %s",
            username,
            resp.status_code,
            resp.error,
            resp.error_code,
        )
        return
    found = False
    for agent in user["agents"]:
        if resp.data["token"] == agent["token"]:
            found = True
    if not found:
        user["agents"].append({"token": resp.data["token"], "username": username})
    json.dump(user, open("user.json", "w"), indent=2)
    return resp.data["token"]


if __name__ == "__main__":
    set_logging()
    user = json.load(open("user.json"))
    logger.info("Starting up conductor, preparing to connect to database")
    logger.info("Connected to database")
    agents = []
    agents_and_clients: dict[str:SpaceTraders] = {}
    ReconConductor(user)
