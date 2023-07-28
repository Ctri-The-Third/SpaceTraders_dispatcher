# the conductor loops every 5 minutes and checks over the status of the universe, and the players, and decides what to do next.
# actions include things like "refreshing market data"
# allocating ships to go mining for ores
# allocating ships to go trading
# and so on.
# we can assume that each agent is based at a different IP Address, and orchestrate accordingly.
import json
import psycopg2
from spacetraders_v2.client_mediator import SpaceTradersMediatorClient as SpaceTraders
from spacetraders_v2.ship import Ship
from spacetraders_v2.models import ShipyardShip
import logging
import time
from dispatcherWK3 import (
    BHVR_RECEIVE_AND_SELL,
    BHVR_EXTRACT_AND_SELL,
    BHVR_RECEIVE_AND_FULFILL,
    BHVR_EXPLORE_CURRENT_SYSTEM,
    BHVR_EXTRACT_AND_TRANSFER,
)


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
            current_stage = stages_per_agent[agent]
            stages_per_agent[agent] = stage_functions[current_stage](client)
        time.sleep(sleep_time)

        sleep_time = 1

    pass


def stage_0(client: SpaceTraders):
    client.ships_view(True)
    # populate the ships from the API
    return 1  # not implemented yet, skip to stage 1
    pass


def stage_1(client: SpaceTraders):
    # activity location is the commander's location.
    ships = client.ships_view()
    agent = client.view_my_self()
    commanders = [ship for ship in ships.values() if ship.role == "COMMAND"]
    for ship in commanders:
        ship: Ship
        set_behaviour(ship.name, BHVR_EXTRACT_AND_SELL)

    extractors = [ship for ship in ships.values() if ship.role == "EXCAVATOR"]
    if len(extractors) >= 5:
        return 2
    else:
        for ship in extractors:
            set_behaviour(ship.name, BHVR_EXTRACT_AND_SELL)
        maybe_ship = maybe_buy_ship(
            client, commanders[0].nav.system_symbol, "SHIP_MINING_DRONE"
        )
        if maybe_ship:
            set_behaviour(maybe_ship.name, BHVR_EXTRACT_AND_SELL)

    # find the number of excavators - if greater than 5, stage = 2

    # else, check how much excavators cost. If we don't know - send the Commander to find out.

    # if we do know, and we can afford an excavator, buy up to 5.

    # set all excavators to extract and sell.
    return 1


def stage_2(client: SpaceTraders):
    ships = client.ships_view()

    haulers = [ship for ship in ships.values() if ship.role == "HAULER"]
    if len(haulers) >= 1:
        return 3
    else:
        maybe_ship = maybe_buy_ship(
            client, ships.values()[0].nav.system_symbol, "SHIP_FREIGHTER"
        )
        if maybe_ship:
            set_behaviour(maybe_ship.name, BHVR_EXTRACT_AND_TRANSFER)
    return 2
    pass


def stage_3(client: SpaceTraders):
    ships = client.ships_view()

    excavators = [ship for ship in ships.values() if ship.role == "EXCAVATOR"]
    for excavator in excavators:
        set_behaviour(excavator.name, BHVR_EXTRACT_AND_TRANSFER)

    haulers = [ship for ship in ships.values() if ship.role == "HAULER"]
    for hauler in haulers:
        set_behaviour(hauler.name, BHVR_RECEIVE_AND_FULFILL)

    if len(ships) <= 50:
        pass

    return 3


def stage_4():
    pass


def set_behaviour(ship_name, behaviour_id):
    sql = """insert into ship_behaviours (ship_name, behaviour_id)
    values (%s, %s) on conflict (ship_name) do update set behaviour_id = %s"""
    cursor = connection.cursor()
    try:
        cursor.execute(sql, (ship_name, behaviour_id, behaviour_id))
    except Exception as e:
        logging.error(e)
        return False


def maybe_buy_ship(client: SpaceTraders, system_symbol, ship_symbol):
    shipyard_wps = client.find_waypoints_by_trait(system_symbol, "SHIPYARD")
    if len(shipyard_wps) == 0:
        return False
    agent = client.view_my_self()
    ship_details = client.view_available_ships_details(shipyard_wps[0])
    if not ship_details:
        return False
    for ship_symbol, detail in ship_details.items():
        detail: ShipyardShip
        if detail.type == ship_symbol:
            if agent.credits > detail.purchase_price:
                resp = client.ships_purchase(shipyard_wps[0], ship_symbol)
                if resp:
                    return resp[0]


def get_agents():
    sql = "select distinct agent_name from ship"
    cur = connection.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    agents_and_tokens = {}
    for agent in user.get("agents"):
        agents_and_tokens[agent["username"]] = agent["token"]
    for row in rows:
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
    user = json.load(open("user.json"))
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
    connection.autocommit = True
    agents = []
    agents_and_clients: dict[str:SpaceTraders] = {}
    master()
