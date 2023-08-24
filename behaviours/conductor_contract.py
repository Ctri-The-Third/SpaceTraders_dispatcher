import sys

sys.path.append(".")

import json, sys

from straders_sdk.client_mediator import SpaceTradersMediatorClient as SpaceTraders
from straders_sdk.ship import Ship
from straders_sdk.contracts import Contract
from straders_sdk.models import ShipyardShip, Waypoint, Shipyard, Survey, System
from straders_sdk.utils import set_logging, waypoint_slicer, try_execute_select
import logging
import time
from dispatcherWK7 import (
    BHVR_EXTRACT_AND_SELL,
    BHVR_RECEIVE_AND_FULFILL,
    EXTRACT_TRANSFER,
    BHVR_EXPLORE_SYSTEM,
    BHVR_REMOTE_SCAN_AND_SURV,
    BHVR_BUY_AND_DELIVER_OR_SELL,
)

BHVR_RECEIVE_AND_FULFILL_OR_SELL = BHVR_RECEIVE_AND_FULFILL

logger = logging.getLogger("conductor")


def run(client: SpaceTraders):
    connection = client.db_client.connection
    agent = client.view_my_self()
    hq_sys_sym = waypoint_slicer(agent.headquarters)

    ships = client.ships_view()
    haulers = [ship for ship in ships.values() if ship.role == "HAULER"]

    asteroid_wp = client.find_waypoints_by_type(hq_sys_sym, "ASTEROID_FIELD")[0]
    cargo_to_transfer = []

    fulfil_wp = None
    contracts = client.view_my_contracts()
    contract_type = "MINING"
    hauler_behaviour = BHVR_RECEIVE_AND_FULFILL
    for con in contracts.values():
        con: Contract
        if con.accepted and not con.fulfilled:
            active_contract = con
            for deliverable in con.deliverables:
                if deliverable.units_fulfilled < deliverable.units_required:
                    fulfil_wp = deliverable.destination_symbol
                    cargo_to_transfer.append(deliverable.symbol)
                    if "ORE" not in cargo_to_transfer:
                        contract_type = "DELIVERY"

    if contract_type == "DELIVERY":
        hauler_behaviour = BHVR_BUY_AND_DELIVER_OR_SELL
        inc_del = [
            deliverable
            for deliverable in active_contract.deliverables
            if deliverable.units_fulfilled < deliverable.units_required
        ]
        hauler_params = {
            "tradegood": cargo_to_transfer[0],
            "quantity": inc_del[0].units_required - inc_del[0].units_fulfilled,
            "fulfil_wp": fulfil_wp,
        }
    else:
        hauler_behaviour = BHVR_RECEIVE_AND_FULFILL
        hauler_params = {}
        if asteroid_wp:
            hauler_params["asteroid_wp"] = asteroid_wp.symbol
            if fulfil_wp:
                hauler_params["fulfil_wp"] = fulfil_wp

    for hauler in haulers:
        set_behaviour(connection, hauler.name, hauler_behaviour, hauler_params)


def get_price_per_distance_for_survey(
    connection, survey_signature: str, source_system: System
) -> list:
    sql = """select mtl.market_symbol, mtl.trade_symbol, mtl.purchase_price, mtl.sell_price, s.x,s.y, sd.signature
, SQRT(POWER((s.x - %s), 2) + POWER((s.y - %s), 2)) as distance
, mtl.sell_price / (SQRT(POWER((s.x - -9380), 2) + POWER((s.y - -10447), 2))+0.01) as value_per_distance
from market_tradegood_listings mtl
join survey_deposits sd on sd.trade_symbol = mtl.trade_symbol
join waypoints w on mtl.market_symbol = w.waypoint_symbol
join systems s on w.system_Symbol = s.system_symbol
where sd.signature = %s
and s.system_symbol != %s
order by value_per_distance desc """
    results = try_execute_select(
        connection,
        sql,
        (source_system.x, source_system.y, survey_signature, source_system.symbol),
    )
    return results


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


if __name__ == "__main__":
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U7-"
    ship_suffix = sys.argv[2] if len(sys.argv) > 2 else "1"
    ship = f"{agent}-{ship_suffix}"

    set_logging()
    user = json.load(open("user.json"))
    for detail in user["agents"]:
        if detail["username"] == agent:
            token = detail["token"]
    st = SpaceTraders(
        token,
        db_host=user["db_host"],
        db_port=user["db_port"],
        db_name=user["db_name"],
        db_user=user["db_user"],
        db_pass=user["db_pass"],
        current_agent_symbol=agent,
    )
    agents = []
    run(st)
