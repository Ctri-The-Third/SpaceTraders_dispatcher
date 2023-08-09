# the conductor loops every 5 minutes and checks over the status of the universe, and the players, and decides what to do next.
# actions include things like "refreshing market data"
# allocating ships to go mining for ores
# allocating ships to go trading
# and so on.
# we can assume that each agent is based at a different IP Address, and orchestrate accordingly.
import json
import psycopg2
from straders_sdk.client_mediator import SpaceTradersMediatorClient as SpaceTraders
from straders_sdk.ship import Ship
from straders_sdk.contracts import Contract
from straders_sdk.models import ShipyardShip, Waypoint, Shipyard
from straders_sdk.utils import set_logging
import logging
import time
from dispatcherWK3 import (
    BHVR_RECEIVE_AND_SELL,
    BHVR_EXTRACT_AND_SELL,
    BHVR_RECEIVE_AND_FULFILL,
    BHVR_EXPLORE_CURRENT_SYSTEM,
    EXTRACT_TRANSFER,
    BHVR_EXTRACT_AND_TRANSFER_ALL,
)

logger = logging.getLogger("conductor")


def master():
    agents_and_clients = get_agents()
    stages_per_agent = {agent: 0 for agent in agents_and_clients}
    # stage 0 - scout costs and such of starting system.
    ## move on once there are db listings for the appropriate system.
    # stage 1 - commander to extract & sell
    ## move on immediately
    # stage 2 - buy freighter - survey, receive & deliver. commander to receive and deliver if idle.
    ## move on once there is one freighter
    # stage 3 - ore hounds - extract & transfer
    ## if there are 40 total ore-hounds, disable extractors
    ## if there are 50 total ore-hounds move on
    # stage 5 - no behaviour.
    stage_functions = [stage_0, stage_1, stage_2, stage_3, stage_4]
    sleep_time = 1
    while True:
        for agent, client in agents_and_clients.items():
            logger.info(f"Agent {agent} is at stage {stages_per_agent[agent]}")
            current_stage = stages_per_agent[agent]
            stages_per_agent[agent] = stage_functions[current_stage](client)
        time.sleep(sleep_time)

        sleep_time = 10

    pass


def stage_0(client: SpaceTraders):
    client.ships_view(True)
    # populate the ships from the API
    # trigger the local commander to go explore the system.

    wayps = client.waypoints_view(client.view_my_self().headquarters)
    if wayps:
        for wayp in wayps:
            for trait in wayp.traits:
                if trait.symbol == "SHIPYARD":
                    return 1  # we can scale!
    commanders = [ship for ship in client.ships.values() if ship.role == "COMMAND"]
    satelites = [ship for ship in client.ships.values() if ship.role == "SATELLITE"]
    for commander in commanders:
        set_behaviour(commander.name, BHVR_EXPLORE_CURRENT_SYSTEM)

    contracts = client.view_my_contracts()
    if len(contracts) == 0:
        client.ship_negotiate(satelites[0])
        contracts = client.view_my_contracts()
    for con in contracts:
        con: Contract
        if not con.accepted:
            client.contract_accept(con.id)
    return 1  # not implemented yet, skip to stage 1
    pass


def stage_1(client: SpaceTraders):
    # scale up to 2 extractors.
    ships = client.ships_view()

    extractors = [ship for ship in ships.values() if ship.role == "EXCAVATOR"]
    if len(extractors) >= 2:
        return 2

    commanders = [ship for ship in ships.values() if ship.role == "COMMAND"]
    for ship in commanders:
        ship: Ship
        set_behaviour(ship.name, BHVR_EXTRACT_AND_SELL)

    for ship in extractors:
        set_behaviour(ship.name, BHVR_EXTRACT_AND_SELL)
    maybe_ship = maybe_buy_ship(
        client, commanders[0].nav.system_symbol, "SHIP_MINING_DRONE"
    )
    if maybe_ship:
        set_behaviour(maybe_ship.name, BHVR_EXTRACT_AND_SELL)
    return 1


def stage_2(client: SpaceTraders):
    # we're at 2 extractors and one commander and it's not bottlenecked on the freighter yet.
    # we need to selectively scale up based on cost per mining power.
    # Move to stage 3 either once we have 5 dedicated excavators, or 2 excavators and one ore hound.
    ships = client.ships_view()
    hq_system = list(client.ships.values())[1].nav.system_symbol
    # 1. decide on what ship to purchase.
    # ore hounds = 25 mining power
    # excavator = 10 mining power

    hounds = [ship for ship in ships.values() if ship.frame.symbol == "FRAME_MINER"]
    commanders = [ship for ship in ships.values() if ship.role == "COMMAND"]
    excavators = [ship for ship in ships.values() if ship.role == "EXCAVATOR"]
    if len(excavators) >= 5 or len(hounds) >= 1:
        return 3
    for ship in commanders:
        set_behaviour(ship.name, BHVR_EXTRACT_AND_SELL)
    for ship in excavators:
        set_behaviour(ship.name, BHVR_EXTRACT_AND_SELL)

    prices = get_ship_prices_in_hq_system(client)

    if (prices.get("SHIP_ORE_HOUND", 99999999) / 25) < prices.get(
        "SHIP_MINING_DRONE", 99999999
    ) / 10:
        maybe_buy_ship(client, hq_system, "SHIP_ORE_HOUND")
    else:
        maybe_buy_ship(client, hq_system, "SHIP_MINING_DRONE")
    return 2


def stage_3(client: SpaceTraders):
    # we're have 1 or 2 surveyors, and 3 or 5 excavators.
    # at this point we want to switch to surveying and hauling, not raw hauling.
    ships = client.ships_view()
    hq_system = list(client.ships.values())[1].nav.system_symbol

    excavators = [ship for ship in ships.values() if ship.role == "EXCAVATOR"]
    hounds = [ship for ship in ships.values() if ship.frame == "FRAME_MINER"]
    haulers = [ship for ship in ships.values() if ship.role == "HAULER"]
    commanders = [ship for ship in ships.values() if ship.role == "COMMAND"]

    # once we're at 30 excavators and 3 haulers, we can move on.
    if len(excavators) >= 30 and len(haulers) >= 3:
        return 4

    #
    # set behaviours. use commander until we have a freighter.
    #
    asteroid_wp = client.find_waypoints_by_type(hq_system, "ASTEROID_FIELD")
    if asteroid_wp:
        behaviour_params = {"asteroid_wp": asteroid_wp[0].symbol}
    for excavator in excavators:
        set_behaviour(excavator.name, EXTRACT_TRANSFER, behaviour_params)
    for hauler in haulers:
        set_behaviour(hauler.name, BHVR_RECEIVE_AND_FULFILL, behaviour_params)
    if len(haulers) == 0:
        for commander in commanders:
            set_behaviour(commander.name, BHVR_RECEIVE_AND_FULFILL, behaviour_params)

    #
    # Scale up to 30 miners and 3 haulers.
    #
    if len(excavators) <= 30:
        prices = get_ship_prices_in_hq_system(client)
        if (prices.get("SHIP_ORE_HOUND", 99999999) / 25) < prices.get(
            "SHIP_MINING_DRONE", 99999999
        ) / 10:
            ship = maybe_buy_ship(client, hq_system, "SHIP_ORE_HOUND")
        else:
            ship = maybe_buy_ship(client, hq_system, "SHIP_MINING_DRONE")

        if ship:
            set_behaviour(ship.name, EXTRACT_TRANSFER, behaviour_params)
    if len(haulers) <= len(hounds) / 10:
        ship = maybe_buy_ship(
            client, excavators[0].nav.system_symbol, "SHIP_LIGHT_HAULER"
        )
        if ship:
            set_behaviour(ship.name, EXTRACT_TRANSFER, behaviour_params)
    return 3


def stage_4(client: SpaceTraders):
    # we're at at 30 excavators and 3 haulers.
    # Ideally we want to start building up hounds, replacing excavators.
    ships = client.ships_view()
    excavators = [ship for ship in ships.values() if ship.role == "EXCAVATOR"]
    drones = [ship for ship in ships.values() if ship.frame == "FRAME_DRONE"]
    hounds = [ship for ship in ships.values() if ship.frame == "FRAME_MINER"]
    haulers = [ship for ship in ships.values() if ship.role == "HAULER"]
    target_hounds = 50
    #
    # for drone in drones:
    #    set_behaviour(drone.name, "DISABLED")
    if len(excavators) >= target_hounds:
        # go through the first $EXCESS drones and disable them.
        for drone in drones[: len(excavators) - target_hounds]:
            set_behaviour(drone.name, "DISABLED")
    if len(hounds) <= target_hounds:
        ship = maybe_buy_ship(client, hounds[0].nav.system_symbol, "SHIP_ORE_HOUND")
        if ship:
            set_behaviour(ship.name, EXTRACT_TRANSFER)
    if len(haulers) <= len(hounds) / 10:
        ship = maybe_buy_ship(client, hounds[0].nav.system_symbol, "SHIP_LIGHT_HAULER")
        if ship:
            set_behaviour(ship.name, BHVR_RECEIVE_AND_FULFILL)

    # switch off mining drones.
    pass


def set_behaviour(ship_symbol, behaviour_id, behaviour_params=None):
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


def maybe_buy_ship(client: SpaceTraders, system_symbol, ship_symbol):
    shipyard_wps = client.find_waypoints_by_trait(system_symbol, "SHIPYARD")
    if not shipyard_wps:
        logging.warning("No shipyards found yet - can't scale.")
        return

    if len(shipyard_wps) == 0:
        return False
    agent = client.view_my_self(True)

    shipyard = client.system_shipyard(shipyard_wps[0])

    if not shipyard:
        return False
    for _, detail in shipyard.ships.items():
        detail: ShipyardShip
        if detail.ship_type == ship_symbol:
            if agent.credits > detail.purchase_price:
                resp = client.ships_purchase(ship_symbol, shipyard_wps[0].symbol)
                if resp:
                    return resp[0]


def get_ship_prices_in_hq_system(client: SpaceTraders):
    hq_system = list(client.ships_view().values())[1].nav.system_symbol

    shipyard_wps = client.find_waypoints_by_trait(hq_system, "SHIPYARD")
    if not shipyard_wps or len(shipyard_wps) == 0:
        return 2
    shipyard_wp: Waypoint = shipyard_wps[0]
    shipyard = client.system_shipyard(shipyard_wp)
    if not shipyard:
        return 2
    shipyard: Shipyard
    return_obj = {}
    for ship_type, ship in shipyard.ships.items():
        ship: ShipyardShip
        return_obj[ship_type] = ship.purchase_price
    return return_obj


def get_agents():
    sql = "select distinct agent_name from ship"
    cur = connection.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    agents_and_tokens = {}
    for agent in user.get("agents"):
        agents_and_tokens[agent["username"]] = agent["token"]
    for row in rows:
        token = agents_and_tokens.get(row[0], None)
        if not token:
            continue
            # skip users for which we don't have tokens
        st = SpaceTraders(
            token=agents_and_tokens.get(row[0], None),
            db_host=user["db_host"],
            db_port=user["db_port"],
            db_name=user["db_name"],
            db_user=user["db_user"],
            db_pass=user["db_pass"],
            current_agent_symbol=row[0],
        )
        agents_and_clients[row[0]] = st
    return agents_and_clients


if __name__ == "__main__":
    set_logging()
    user = json.load(open("user.json"))
    logger.info("Starting up conductor, preparing to connect to database")
    connection = psycopg2.connect(
        host=user["db_host"],
        port=user["db_port"],
        database=user["db_name"],
        user=user["db_user"],
        password=user["db_pass"],
        connect_timeout=3,
        keepalives=1,
        keepalives_idle=5,
        keepalives_interval=2,
        keepalives_count=2,
    )
    logger.info("Connected to database")
    connection.autocommit = True
    agents = []
    agents_and_clients: dict[str:SpaceTraders] = {}
    master()
