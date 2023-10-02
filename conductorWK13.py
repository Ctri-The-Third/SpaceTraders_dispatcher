import json
import psycopg2, psycopg2.sql
from straders_sdk.local_response import LocalSpaceTradersRespose
from straders_sdk.models import Shipyard, ShipyardShip, Waypoint
from straders_sdk.ship import Ship
from straders_sdk.client_mediator import SpaceTradersMediatorClient as SpaceTraders
from datetime import datetime, timedelta
import sys
import hashlib
import re
from straders_sdk.utils import (
    set_logging,
    waypoint_slicer,
    try_execute_select,
    try_execute_upsert,
)
import logging
from dispatcherWK12 import (
    BHVR_EXTRACT_AND_SELL,
    BHVR_RECEIVE_AND_FULFILL,
    BHVR_RECEIVE_AND_REFINE,
)

logger = logging.getLogger(__name__)


class Conductor:

    """This class will manage the recon agents and their behaviour."""

    def __init__(
        self,
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
        self.agents_and_tokens = {
            agent_obj["username"]: agent_obj["token"]
            for agent_obj in user.get("agents")
        }

    def run(self):
        #
        # * scale regularly and set defaults
        # * progress missions
        last_hourly_update = datetime.now() - timedelta(hours=2)
        last_daily_update = datetime.now() - timedelta(days=2)
        #
        # hourly calculations of profitable things, assign behaviours and tasks
        #
        # daily reset uncharted waypoints.
        self.asteroid_wp: Waypoint = None
        all_commanders = []

        if last_daily_update < datetime.now() - timedelta(days=1):
            self.daily_update()

        if last_hourly_update < datetime.now() - timedelta(hours=1):
            self.hourly_update()

        self.minutely_update()

    def hourly_update(self):
        for agent, token in self.agents_and_tokens.items():
            st = self.client
            st.set_current_agent(agent, token)

            hq = st.view_my_self().headquarters
            hq_sys = waypoint_slicer(hq)
            resp = st.find_waypoints_by_type_one(hq_sys, "ASTEROID_FIELD")
            self.asteroid_wp = resp
        # determine current starting asteroid
        # determine top 2 goods to export
        # assign a single trader to buy/sell behaviour
        # assign a single extractor to extract/sell locally
        # assign a single extractor to extract/sell remotely
        # if there is a refiner, assign a single extractor to extract/transfer

        # how do we decide on surveyors?
        pass

    def daily_update(self):
        sql = """
            update waypoints w set checked = false where waypoint_symbol in (
                select waypoint_symbol from waypoint_traits wt where wt.trait_symbol = 'UNCHARTED'
            );
            delete from waypoint_traits WT where wt.trait_symbol = 'UNCHARTED';"""
        try_execute_upsert(self.connection, sql, [])

    def minutely_update(self):
        """This method handles ship scaling and assigning default behaviours."""
        for agent, token in self.agents_and_tokens.items():
            st = self.client
            st.set_current_agent(agent, token)

            st.token = token
            st.current_agent = st.view_my_self()
            ships = st.ships_view()

            satelites = [ship for ship in ships.values() if ship.role == "SATELLITE"]
            haulers = [ship for ship in ships.values() if ship.role == "HAULER"]
            commanders = [ship for ship in ships.values() if ship.role == "COMMAND"]
            hounds = [
                ship for ship in ships.values() if ship.frame.symbol == "FRAME_MINER"
            ]
            refiners = [ship for ship in ships.values() if ship.role == "REFINERY"]

            #
            # this can be its own "scale up" method
            #
            behaviour_params = {"asteroid_wp": self.asteroid_wp.symbol}
            ships_we_might_buy = []
            # stage
            if len(hounds) <= 15:
                new_ship = maybe_buy_ship_hq_sys(st, "SHIP_ORE_HOUND")
                new_behaviour = BHVR_EXTRACT_AND_SELL
                ships_we_might_buy = ["SHIP_ORE_HOUND"]
            # stage 4
            elif len(hounds) < 30 or len(refiners) < 1 or len(haulers) < 6:
                # if we did everything at the first availble price, we'd get 30 ore hounds before we got any haulers
                ships_we_might_buy = [
                    "SHIP_PROBE",
                    "SHIP_ORE_HOUND",
                    "SHIP_LIGHT_HAULER",
                ]
                if len(haulers) < len(hounds) / 5:
                    new_ship = maybe_buy_ship_hq_sys(st, "SHIP_LIGHT_HAULER")
                    new_behaviour = BHVR_RECEIVE_AND_FULFILL
                elif len(hounds) < 30:
                    new_ship = maybe_buy_ship_hq_sys(st, "SHIP_ORE_HOUND")
                    new_behaviour = BHVR_EXTRACT_AND_SELL
                elif len(refiners) < 1:
                    new_ship = maybe_buy_ship_hq_sys(st, "SHIP_REFINERY")
                    new_behaviour = BHVR_RECEIVE_AND_REFINE
            elif len(hounds) <= 50 or len(refiners) < 2 or len(haulers) < 10:
                ships_we_might_buy = [
                    "SHIP_PROBE",
                    "SHIP_ORE_HOUND",
                    "SHIP_LIGHT_HAULER",
                    "SHIP_HEAVY_HAULER",
                    "SHIP_COMMAND_FRIGATE",
                    "SHIP_REFINERY",
                ]
                if len(hounds) < 50:
                    new_ship = maybe_buy_ship_hq_sys(st, "SHIP_ORE_HOUND")
                    new_behaviour = BHVR_EXTRACT_AND_SELL
                elif len(refiners) < 2:
                    new_ship = maybe_buy_ship_hq_sys(st, "SHIP_REFINERY")
                    new_behaviour = BHVR_RECEIVE_AND_REFINE
                elif len(haulers) < 10:
                    new_ship = maybe_buy_ship_hq_sys(st, "SHIP_HAULER")
                    new_behaviour = BHVR_RECEIVE_AND_FULFILL
                pass

            if new_ship:
                set_behaviour(
                    self.connection,
                    new_ship.name,
                    new_behaviour,
                    behaviour_params=behaviour_params,
                )
        pass


def set_behaviour(connection, ship_symbol, behaviour_id, behaviour_params=None):
    sql = """INSERT INTO ship_behaviours (ship_symbol, behaviour_id, behaviour_params)
    VALUES (%s, %s, %s)
    ON CONFLICT (ship_symbol) DO UPDATE SET
        behaviour_id = %s,
        behaviour_params = %s
    """
    cursor = connection.cursor()
    behaviour_params_s = (
        json.dumps(behaviour_params) if behaviour_params is not None else None
    )

    try:
        cursor.execute(
            sql,
            (
                ship_symbol,
                behaviour_id,
                behaviour_params_s,
                behaviour_id,
                behaviour_params_s,
            ),
        )
    except Exception as err:
        logging.error(err)
        return False


def log_task(
    connection,
    behaviour_id: str,
    requirements: list,
    target_system: str,
    priority=5,
    agent_symbol=None,
    behaviour_params=None,
    expiry=None,
    specific_ship_symbol=None,
):
    behaviour_params = {} if not behaviour_params else behaviour_params
    param_s = json.dumps(behaviour_params)
    hash_str = hashlib.md5(
        f"{behaviour_id}-{target_system}-{priority}-{behaviour_params}-{expiry}-{specific_ship_symbol}".encode()
    ).hexdigest()
    sql = """ INSERT INTO public.ship_tasks(
	task_hash, requirements, expiry, priority, agent_symbol, claimed_by, behaviour_id, target_system, behaviour_params)
	VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    on conflict(task_hash) DO NOTHING
    """

    resp = try_execute_upsert(
        connection,
        sql,
        (
            hash_str,
            requirements,
            expiry,
            priority,
            agent_symbol,
            specific_ship_symbol,
            behaviour_id,
            target_system,
            param_s,
        ),
    )
    return resp or True


def maybe_buy_ship_hq_sys(client: SpaceTraders, ship_symbol) -> "Ship" or None:
    system_symbol = waypoint_slicer(client.view_my_self().headquarters)

    shipyard_wps = client.find_waypoints_by_trait(system_symbol, "SHIPYARD")
    if not shipyard_wps:
        logging.warning("No shipyards found yet - can't scale.")
        return

    if len(shipyard_wps) == 0:
        return False
    agent = client.view_my_self()

    shipyard = client.system_shipyard(shipyard_wps[0])
    return _maybe_buy_ship(client, shipyard, ship_symbol)



def _maybe_buy_ship(client: SpaceTraders, shipyard: Shipyard, ship_symbol: str):
    agent = client.view_my_self()

    if not shipyard:
        return False
    for _, detail in shipyard.ships.items():
        detail: ShipyardShip
        if detail.ship_type == ship_symbol:
            if not detail.purchase_price:
                return LocalSpaceTradersRespose(
                    f"We don't have price information for this shipyard. {shipyard.waypoint}",
                    0,
                    0,
                    "conductorWK7.maybe_buy_ship",
                )
            if agent.credits > detail.purchase_price:
                resp = client.ships_purchase(ship_symbol, shipyard.waypoint)
                if resp:
                    return resp[0]


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
    if not resp:
        return resp
    return resp.data["token"]


if __name__ == "__main__":
    set_logging()
    user = json.load(open("user.json"))
    logger.info("Starting up conductor, preparing to connect to database")
    logger.info("Connected to database")
    agents = []
    agents_and_clients: dict[str:SpaceTraders] = {}
    Conductor().run()
