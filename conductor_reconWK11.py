import json
import psycopg2, psycopg2.sql
from straders_sdk.local_response import LocalSpaceTradersRespose
from straders_sdk.models import Shipyard, ShipyardShip, Waypoint
from straders_sdk.client_mediator import SpaceTradersMediatorClient as SpaceTraders
from behaviours.receive_and_fulfill import (
    ReceiveAndFulfillOrSell_3,
    BEHAVIOUR_NAME as BHVR_RECEIVE_AND_FULFILL,
)
import hashlib
import re
from straders_sdk.utils import (
    set_logging,
    waypoint_slicer,
    try_execute_select,
    try_execute_upsert,
)
import logging
from dispatcherWK7 import BHVR_EXPLORE_SYSTEM


RECON_AGENTS_MAX = 10
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
        agent_regex = re.compile(f"{recon_prefix}.*")
        match = agent_regex.match("ZTRI-1")
        self.agents_and_tokens = {
            agent_obj["username"]: agent_obj["token"]
            for agent_obj in user.get("agents")
            if agent_regex.match(agent_obj["username"]) and "token" in agent_obj
        }
        if len(self.agents_and_tokens) < max_agents:
            i = len(agents)
            for i in range(max_agents - len(self.agents_and_tokens)):
                agent_name = f"{recon_prefix}-{i}-"
                token = register_and_store_user(agent_name)
                i += 1
                if not token:
                    continue
                self.agents_and_tokens["username"] = token

    def run(self):
        asteroid_wp: Waypoint = None
        all_commanders = []
        for agent_name, token in self.agents_and_tokens.items():
            self.client.token = token
            self.client.api_client.token = token
            agent = self.client.view_my_self()

            hq_sys = waypoint_slicer(self.client.view_my_self().headquarters)
            if not asteroid_wp:
                resp = self.client.find_waypoints_by_type(hq_sys, "ASTEROID_FIELD")
                if resp:
                    asteroid_wp = resp[0]
            st = self.client
            self.client.api_client.token = token
            self.client.current_agent_symbol = agent_name
            agent = st.view_my_self(True)
            ships = st.ships_view()
            commanders = [ship for ship in ships.values() if ship.role == "COMMAND"]
            satellites = [ship for ship in ships.values() if ship.role == "SATELLITE"]
            print(f"{agent.symbol} - {agent.credits}")
            maybe_ship = True
            while maybe_ship:
                maybe_ship = maybe_buy_ship_hq_sys(self.client, "SHIP_PROBE")
                if maybe_ship:
                    satellites.append(maybe_ship)

            for ship in commanders:
                all_commanders.append(ship)
                self.set_behaviour(
                    ship.name,
                    BHVR_RECEIVE_AND_FULFILL,
                    {"asteroid_wp": asteroid_wp.symbol},
                )
            for satelite in satellites:
                self.set_behaviour(satelite.name, BHVR_EXPLORE_SYSTEM)
        self.maybe_explore_starting_system(all_commanders[0].name)

        sql = """select distinct system_symbol 
	from market_tradegood mt 
	join waypoints w on mt.market_waypoint = w.waypoint_symbol
	left join market_tradegood_listings mtl on mt.market_waypoint = mtl.market_symbol and mt.symbol = mtl.trade_symbol
	where symbol IN ( 'MOUNT_MINING_LASER_II', 'MOUNT_MINING_LASER_III' ,'MOUNT_SURVEYOR_II') 
	and mtl.trade_symbol is null
union
(select * from mkt_shpyrds_systems_to_visit_first limit 20)"""
        systems = try_execute_select(self.connection, sql, [])
        if systems:
            for system in systems:
                log_task(
                    self.connection,
                    BHVR_EXPLORE_SYSTEM,
                    ["DRONE"],
                    system[0],
                    5,
                    None,
                    {"target_sys": system[0]},
                )

    def maybe_explore_starting_system(self, ship_symbol):
        sql = """with starting_systems as (
select distinct system_symbol from agents a join waypoints w on a.headquarters = w.waypoint_Symbol
),
relevant_market_info as (
select system_symbol, m.symbol, mtl.* from market m 
left join market_tradegood_listings mtl on mtl.market_symbol = m.symbol
where m.system_symbol in (select * from starting_systems ) 

	)
	select system_symbol, symbol, count (market_symbol) 
	from relevant_market_info 
	group by 1 , 2 
	having count(market_symbol) = 0 """
        resp = try_execute_select(self.connection, sql, [])
        if len(resp) > 0:
            task = log_task(
                self.connection,
                BHVR_EXPLORE_SYSTEM,
                [],
                resp[0][0],
                5,
                None,
                {"target_sys": resp[0][0]},
                specific_ship_symbol=ship_symbol,
            )

    def set_behaviour(self, ship_symbol, behaviour_id, behaviour_params=None):
        sql = """INSERT INTO ship_behaviours (ship_symbol, behaviour_id, behaviour_params)
        VALUES (%s, %s, %s)
        ON CONFLICT (ship_symbol) DO UPDATE SET
            behaviour_id = %s,
            behaviour_params = %s
        """
        cursor = self.client.db_client.connection.cursor()
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


def maybe_buy_ship_hq_sys(client: SpaceTraders, ship_symbol):
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
    ReconConductor(user).run()
