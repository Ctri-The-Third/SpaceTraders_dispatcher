import sys

sys.path.append(".")

import json, sys
import hashlib
from straders_sdk.client_mediator import SpaceTradersMediatorClient as SpaceTraders
from straders_sdk.ship import Ship
from straders_sdk.contracts import Contract
from straders_sdk.models import ShipyardShip, Waypoint, Shipyard, Survey, System
from straders_sdk.utils import (
    set_logging,
    waypoint_slicer,
    try_execute_select,
    try_execute_upsert,
)
from datetime import datetime, timedelta
import logging
import time
from dispatcherWK8 import (
    BHVR_EXTRACT_AND_SELL,
    BHVR_RECEIVE_AND_FULFILL,
    BHVR_EXTRACT_AND_TRANSFER_OR_SELL,
    BHVR_EXPLORE_SYSTEM,
    BHVR_REMOTE_SCAN_AND_SURV,
    BHVR_RECEIVE_AND_REFINE,
)

BHVR_RECEIVE_AND_FULFILL_OR_SELL = BHVR_RECEIVE_AND_FULFILL

logger = logging.getLogger("conductor")


def run(client: SpaceTraders):
    connection = client.db_client.connection
    agent = client.view_my_self()
    if agent.headquarters is None or agent.headquarters == "":
        agent = client.view_my_self(True)
    hq_sys_sym = waypoint_slicer(agent.headquarters)

    ships = client.ships_view()
    # excavators = [ship for ship in ships.values() if ship.role == "EXCAVATOR"]
    drones = [ship for ship in ships.values() if ship.frame.symbol == "FRAME_DRONE"]
    hounds = [ship for ship in ships.values() if ship.frame.symbol == "FRAME_MINER"]

    haulers = [ship for ship in ships.values() if ship.role == "HAULER"]
    refiners = [ship for ship in ships.values() if ship.role == "REFINERY"]

    target_miners = 30
    excavators = (hounds + drones)[0:target_miners]
    drones_padding = target_miners - len(hounds)
    active_drones = drones[
        0:drones_padding
    ]  # identify the target drones (included in excavators already)
    spare_drones = drones[drones_padding:]  # switch these ones off.

    asteroid_wp = client.find_waypoints_by_type(hq_sys_sym, "ASTEROID_FIELD")[0]
    survey = client.find_survey_best(asteroid_wp.symbol)
    values = None
    extraction_params = None
    delivery_params = None

    if survey:
        survey: Survey
        values = get_price_per_distance_for_survey(
            connection, survey.signature, client.systems_view_one(hq_sys_sym)
        )
    if len(refiners) >= 0:
        extraction_params = {
            "asteroid_wp": asteroid_wp.symbol,
            "cargo_to_transfer": ["IRON_ORE"],
        }
        other_extraction_params = {"asteroid_wp": asteroid_wp.symbol}

        transfer_params = {"asteroid_wp": asteroid_wp.symbol}
        extractors_per_refiner = 5
        extractors_per_hauler = 2

        hauler_extractors = excavators[
            0 : len(haulers) * extractors_per_hauler
            + len(refiners) * extractors_per_refiner
        ]
        other_extractors = excavators[
            len(haulers) * extractors_per_hauler
            + len(refiners) * extractors_per_refiner :
        ]
    elif values:
        target_info = values[0]
        target_market = target_info[0]
        other_extraction_params = {"asteroid_wp": asteroid_wp.symbol}
        extraction_params = {
            "asteroid_wp": asteroid_wp.symbol,
            "cargo_to_transfer": [
                target_info[1],
            ],
        }
        transfer_params = {
            "asteroid_wp": asteroid_wp.symbol,
            "market_wp": target_market,
        }

        extractors_per_hauler = 2
    hauler_extractors = excavators[0 : len(haulers) * extractors_per_hauler]
    other_extractors = excavators[len(haulers) * extractors_per_hauler :]
    for excavator in hauler_extractors:
        set_behaviour(
            connection,
            excavator.name,
            BHVR_EXTRACT_AND_TRANSFER_OR_SELL,
            extraction_params,
        )
    for hauler in haulers:
        set_behaviour(
            connection,
            hauler.name,
            BHVR_RECEIVE_AND_FULFILL_OR_SELL,
            transfer_params,
        )
    for refiner in refiners:
        set_behaviour(
            connection,
            refiner.name,
            BHVR_RECEIVE_AND_REFINE,
            other_extraction_params,
        )
    for excavator in other_extractors:
        set_behaviour(
            connection,
            excavator.name,
            BHVR_EXTRACT_AND_SELL,
            other_extraction_params,
        )
    for excavator in spare_drones:
        set_behaviour(connection, excavator.name, BHVR_EXPLORE_SYSTEM)


def log_task(
    connection,
    behaviour_id: str,
    requirements: list,
    target_system: str,
    priority=5,
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
	task_hash, requirements, expiry, priority, claimed_by, behaviour_id, target_system, behaviour_params)
	VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    try_execute_select(
        connection,
        sql,
        (
            hash_str,
            requirements,
            expiry,
            priority,
            None,
            behaviour_id,
            target_system,
            param_s,
        ),
    )


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
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_suffix = sys.argv[2] if len(sys.argv) > 2 else "1"
    ship = f"{agent}-{ship_suffix}"

    set_logging()
    user = json.load(open("user.json"))

    for detail in user["agents"]:
        if not "username" in detail or not "token" in detail:
            continue
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
