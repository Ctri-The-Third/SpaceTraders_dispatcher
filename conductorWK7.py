# the conductor loops every 5 minutes and checks over the status of the universe, and the players, and decides what to do next.
# actions include things like "refreshing market data"
# allocating ships to go mining for ores
# allocating ships to go trading
# and so on.
# we can assume that each agent is based at a different IP Address, and orchestrate accordingly.
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
from itertools import zip_longest
from behaviours.conductor_mining import run as refresh_stale_waypoints
import logging
import time
from datetime import datetime, timedelta
from dispatcherWK7 import (
    BHVR_EXTRACT_AND_SELL,
    BHVR_RECEIVE_AND_FULFILL,
    EXTRACT_TRANSFER,
    BHVR_EXPLORE_SYSTEM,
    BHVR_REMOTE_SCAN_AND_SURV,
    BHVR_MONITOR_CHEAPEST_PRICE,
    BHVR_BUY_AND_DELIVER_OR_SELL,
)

BHVR_RECEIVE_AND_FULFILL_OR_SELL = (
    "Placeholder, receive & fulfill or sell (update in conductor)"
)

logger = logging.getLogger("conductor")


def master():
    agents_and_clients = get_agents()
    starting_stage = 0
    stages_per_agent = {agent: starting_stage for agent in agents_and_clients}
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
            try:
                stages_per_agent[agent] = stage_functions[current_stage](client)
            except Exception as err:
                logger.error(err)
                continue
        time.sleep(sleep_time)

        sleep_time = 60

    pass


def stage_0(client: SpaceTraders):
    client.ships_view(True)

    # populate the ships from the API
    # trigger the local commander to go explore the system.
    sys_wp = waypoint_slicer(client.view_my_self().headquarters)
    wayps = client.waypoints_view(sys_wp)
    satelites = [ship for ship in client.ships.values() if ship.role == "SATELLITE"]

    contracts = client.view_my_contracts()
    if len(contracts) == 0:
        client.ship_negotiate(satelites[0])
        contracts = client.view_my_contracts()
    for con in contracts.values():
        con: Contract
        if not con.accepted and should_we_accept_contract(client, con):
            client.contract_accept(con.id)

    if wayps:
        for wayp in wayps.values():
            for trait in wayp.traits:
                if trait.symbol == "SHIPYARD":
                    return 1  # we can scale!

    commanders = [ship for ship in client.ships.values() if ship.role == "COMMAND"]
    for commander in commanders:
        set_behaviour(commander.name, BHVR_EXPLORE_SYSTEM, {"target_sys": sys_wp})

    for satelite in satelites:
        set_behaviour(satelite.name, BHVR_REMOTE_SCAN_AND_SURV, {})

    return 1


def stage_1(client: SpaceTraders):
    # scale up to 2 extractors.
    ships = client.ships_view()
    agent = client.view_my_self()
    hq_sys = waypoint_slicer(agent.headquarters)
    shipyard_wp = client.find_waypoints_by_trait(hq_sys, "SHIPYARD")[0]
    # commander behaviour

    extractors = [ship for ship in ships.values() if ship.role == "EXCAVATOR"]
    if len(extractors) >= 2:
        return 2

    satelites = [ship for ship in ships.values() if ship.role == "SATELLITE"]
    commanders = [ship for ship in ships.values() if ship.role == "COMMAND"]
    for ship in commanders:
        ship: Ship
        # if refresh_instruction returns something, do that, otherwise:
        set_behaviour(ship.name, BHVR_EXTRACT_AND_SELL)

    for ship in satelites:
        set_behaviour(
            ship.name, BHVR_REMOTE_SCAN_AND_SURV, {"asteroid_wp": shipyard_wp.symbol}
        )

    for ship in extractors:
        set_behaviour(ship.name, BHVR_EXTRACT_AND_SELL)
    maybe_ship = maybe_buy_ship_hq_sys(client, "SHIP_MINING_DRONE")
    if maybe_ship:
        set_behaviour(maybe_ship.name, BHVR_EXTRACT_AND_SELL)
    return 1


def stage_2(client: SpaceTraders):
    # we're at 2 extractors and one commander and it's not bottlenecked on the freighter yet.
    # we need to selectively scale up based on cost per mining power.
    # Move to stage 3 either once we have 5 dedicated excavators, or 2 excavators and one ore hound.
    ships = client.ships_view()
    agent = client.view_my_self()
    ships = client.ships_view()
    hq_sys = waypoint_slicer(agent.headquarters)
    shipyard_wp = client.find_waypoints_by_trait(hq_sys, "SHIPYARD")[0]
    wayps = client.systems_view_one(hq_sys)
    wayp = client.find_waypoints_by_type(hq_sys, "ASTEROID_FIELD")[0]
    if not wayp:
        logger.warning("No asteroid field found yet shouldn't happen.")

    # 1. decide on what ship to purchase.
    # ore hounds = 25 mining power
    # excavator = 10 mining power
    satelites = [ship for ship in ships.values() if ship.role == "SATELLITE"]
    hounds = [ship for ship in ships.values() if ship.frame.symbol == "FRAME_MINER"]
    commanders = [ship for ship in ships.values() if ship.role == "COMMAND"]
    excavators = [ship for ship in ships.values() if ship.role == "EXCAVATOR"]
    if len(excavators) >= 5 or len(hounds) >= 1:
        return 3
    for ship in commanders:
        set_behaviour(ship.name, BHVR_EXTRACT_AND_SELL, {"asteroid_wp": wayp.symbol})
    for ship in excavators:
        set_behaviour(ship.name, BHVR_EXTRACT_AND_SELL, {"asteroid_wp": wayp.symbol})
    for ship in satelites:
        set_behaviour(
            ship.name, BHVR_REMOTE_SCAN_AND_SURV, {"asteroid_wp": shipyard_wp.symbol}
        )

    ship_to_buy = what_ship_should_i_buy(client, "SHIP_ORE_HOUND")
    ship = maybe_buy_ship_hq_sys(client, ship_to_buy)

    return 2


def stage_3(client: SpaceTraders):
    # we're have 1 or 2 surveyors, and 3 or 5 excavators.
    # at this point we want to switch to surveying and extracting, not raw extracting.

    #
    # PREFLIGHT AND DATA REFRESH
    #

    agent = client.view_my_self()
    hq_wp = agent.headquarters
    hq_sys = waypoint_slicer(hq_wp)
    shipyard_wp = client.find_waypoints_by_trait(hq_sys, "SHIPYARD")[0]
    asteroid_wp = client.find_waypoints_by_type(hq_sys, "ASTEROID_FIELD")[0]

    if is_market_data_stale(client, asteroid_wp.symbol):
        logger.warning("Market data is stale, refresh behaviour not implemented.")

    if are_surveys_weak(client, asteroid_wp.symbol):
        logger.warning("Surveys are weak, refresh behaviour not implemented")

    if is_shipyard_stale(client, shipyard_wp):
        client.system_shipyard(shipyard_wp, True)
    process_contracts(client)
    #
    # SHIP SORTING
    #
    ships = client.ships_view()

    excavators = [ship for ship in ships.values() if ship.role == "EXCAVATOR"]
    hounds = [ship for ship in ships.values() if ship.frame == "FRAME_MINER"]
    haulers = [ship for ship in ships.values() if ship.role == "HAULER"]
    commanders = [ship for ship in ships.values() if ship.role == "COMMAND"]
    satelites = [ship for ship in ships.values() if ship.role == "SATELLITE"]

    extractors_per_hauler = 10
    # once we're at 30 excavators and 3 haulers, we can move on.
    if (
        len(excavators) >= 30
        and len(haulers) >= len(excavators) // extractors_per_hauler
    ):
        return 4

    #
    # SETTING PARAMETERS & HAULER PREPARING
    #
    extractor_params = {}
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
        if len(cargo_to_transfer) > 0:
            extractor_params["cargo_to_transfer"] = cargo_to_transfer

            if fulfil_wp:
                hauler_params["fulfil_wp"] = fulfil_wp

    if asteroid_wp:
        extractor_params["asteroid_wp"] = asteroid_wp.symbol

    #
    # APPLY BEHAVIOURS. use commander until we have a freighter.
    #

    for excavator in excavators:
        set_behaviour(excavator.name, EXTRACT_TRANSFER, extractor_params)
    for hauler in haulers:
        set_behaviour(hauler.name, hauler_behaviour, hauler_params)
    for satelite in satelites:
        set_behaviour(
            satelite.name,
            BHVR_REMOTE_SCAN_AND_SURV,
            {"asteroid_wp": shipyard_wp.symbol},
        )
    for commander in commanders:
        # if there's no hauler, do that.
        if len(haulers) == 0:
            set_behaviour(commander.name, BHVR_RECEIVE_AND_FULFILL, hauler_params)
        else:
            # do the refresh behaviour
            set_behaviour(commander.name, EXTRACT_TRANSFER, extractor_params)
    #
    # Scale up to 30 miners and 3 haulers. Prioritise a hauler if we've got too many drones.
    #
    if len(haulers) <= (len(excavators) / extractors_per_hauler):
        ship = maybe_buy_ship_hq_sys(client, "SHIP_LIGHT_HAULER")
        if ship:
            set_behaviour(ship.name, BHVR_RECEIVE_AND_FULFILL, hauler_params)
    elif len(excavators) <= 30:
        prices = get_ship_prices_in_hq_system(client)
        for ship, price in prices.items():
            if price is None:
                logger.warning(
                    "Couldn't get price for %s - unable to buy ne ships in stage 3, skipping",
                    ship,
                )
                return 3
        if (prices.get("SHIP_ORE_HOUND", 99999999) / 25) < prices.get(
            "SHIP_MINING_DRONE", 99999999
        ) / 10:
            ship = maybe_buy_ship_hq_sys(
                client, what_ship_should_i_buy(client, "SHIP_ORE_HOUND")
            )
        else:
            ship = maybe_buy_ship_hq_sys(
                client, what_ship_should_i_buy(client, "SHIP_MINING_DRONE")
            )

        if ship:
            set_behaviour(ship.name, EXTRACT_TRANSFER, extractor_params)

    return 3


def stage_4(client: SpaceTraders):
    # we're at at 30 excavators and 3 haulers.
    # Ideally we want to start building up hounds, replacing excavators.
    # we also assume that the starting system is drained of resources, so start hauling things out-of-system.
    agent = client.view_my_self()
    # hq_sys_sym = waypoint_slicer(agent.headquarters)
    connection = client.db_client.connection
    ships = client.ships_view()
    asteroid_wp = client.find_waypoints_by_type(
        waypoint_slicer(agent.headquarters), "ASTEROID_FIELD"
    )[0]
    excavators = [ship for ship in ships.values() if ship.role == "EXCAVATOR"]
    drones = [ship for ship in ships.values() if ship.frame.symbol == "FRAME_DRONE"]
    hounds = [ship for ship in ships.values() if ship.frame.symbol == "FRAME_MINER"]
    haulers = [ship for ship in ships.values() if ship.role == "HAULER"]
    satelites = [ship for ship in ships.values() if ship.role == "SATELLITE"]

    refiners = [
        ship
        for ship in ships.values()
        if ship.frame.symbol == "SHIP_REFINING_FREIGHTER"
    ]
    target_hounds = 50
    target_refiners = 1
    extractors_per_hauler = 10
    # once we're at 30 excavators and 3 haulers, we can move on.
    if (
        len(hounds) >= target_hounds
        and len(haulers) >= len(excavators) / extractors_per_hauler
    ):
        return 5
    # note at stage 4, behaviour should be handled less frequently, based on compiled stuff - see conductor_mining.py

    ships_we_might_buy = [
        "SHIP_PROBE",
        "SHIP_ORE_HOUND",
        "SHIP_REFINING_FREIGHTER",
        "SHIP_LIGHT_HAULER",
    ]
    for ship, target in zip_longest(satelites, ships_we_might_buy, fillvalue=None):
        if not ship or not target:
            break
        behaviour_params = {"ship_type": target}
        set_behaviour(ship.name, BHVR_MONITOR_CHEAPEST_PRICE, behaviour_params)
    if len(satelites) < len(ships_we_might_buy):
        maybe_buy_ship_hq_sys(client, "SHIP_PROBE")

    if len(haulers) <= min(len(excavators), target_hounds) / extractors_per_hauler:
        hauler_params = {"asteroid_wp": asteroid_wp.symbol}
        ship = maybe_buy_ship(
            client,
            connection,
            "SHIP_LIGHT_HAULER",
        )
        if ship:
            set_behaviour(ship.name, BHVR_RECEIVE_AND_FULFILL, hauler_params)
    # then either buy a refining freighter, or an ore hound
    if len(refiners) < target_refiners:
        ship = maybe_buy_ship(client, connection, "SHIP_REFINING_FREIGHTER")
        if ship:
            set_behaviour(ship.name, BHVR_RECEIVE_AND_FULFILL)
    elif len(hounds) <= target_hounds:
        ship = maybe_buy_ship(client, connection, "SHIP_ORE_HOUND")
        if ship:
            set_behaviour(
                ship.name, EXTRACT_TRANSFER, {"asteroid_wp": asteroid_wp.symbol}
            )

    return 4
    # switch off mining drones.
    pass


def refresh_materialised_views(connection):
    sql = """refresh materialized view mat_session_stats;"""
    try_execute_select(connection, sql, ())


def refresh_uncharted_systems(connection):
    sql = """update waypoints w
set checked = False where 
w.waypoint_Symbol in (
select w.waypoint_symbol from waypoints w join waypoint_traits wt on w.waypoint_symbol = wt.waypoint_symbol
where w.checked = True  
group by 1

having count (case when wt.trait_symbol = 'UNCHARTED' then 1 else null end ) > 0
	)"""
    try_execute_upsert(connection, sql, ())


def what_ship_should_i_buy(
    client: SpaceTraders,
    default_ship_to_buy=None,
    refresh=False,
    speed_over_efficiency=True,
) -> str:
    # I assume this is mining but who knows.
    order_by = "cph" if speed_over_efficiency else "cpr"
    connection.cursor()
    sql = psycopg2.sql.SQL(
        """with total_cph as (select agent_name, avg(credits_earned) as avg_cph from agent_credits_per_hour acph
where acph.event_hour >= now() at time zone 'utc' - interval '6 hours'
group by 1 )

select stp.agent_name, round(avg_cph,2),  coalesce(stp.shipyard_type, sp.ship_type)
, coalesce(stp.best_price,sp.best_price) as best_price
, coalesce(stp.count_of_ships, 0 ) as count_of_ships
, coalesce(earnings,0) as earnings
, coalesce(requests,0) as requests
, coalesce(sessions,0) as sessions
, round(coalesce(cph,0),2) as cph
, round(coalesce(cpr,0),2) as cpr from shipyard_type_performance stp
left join total_cph tc on stp.agent_name = tc.agent_name 
full outer join shipyard_prices sp on stp.shipyard_type = sp.ship_type

where stp.agent_name  = %s or stp.agent_name is null
order by {} desc, sp.ship_type """
    ).format(psycopg2.sql.Identifier(order_by))
    rows = try_execute_select(connection, sql, (client.current_agent_symbol,))
    if not rows:
        logging.error(
            "Couldn't get shipyard prices and performance stats becase %s", rows.error
        )
        return default_ship_to_buy or "SHIP_MINING_DRONE"
    total_cph = rows[0][1]
    if total_cph is None:
        logger.warning("No CPH data found! Refresh the materialised views.")
        return default_ship_to_buy or "SHIP_MINING_DRONE"
    best_ship_to_buy = default_ship_to_buy
    if default_ship_to_buy:
        found_row = None
        for row in rows:
            if row[2] == default_ship_to_buy:
                found_row = row
                break
        if not found_row:
            return default_ship_to_buy or "SHIP_MINING_DRONE"
        best_ship_to_buy = found_row[2]
        cost = found_row[3] or sys.maxsize
    else:
        best_ship_to_buy = rows[0][2]
        cost = rows[0][3] or sys.maxsize

    hours_to_save_for_best_ship = cost / total_cph

    for ship in rows:
        if not ship[3]:
            continue
        new_cost = ship[3] + cost
        new_time = new_cost / total_cph
        if new_time < hours_to_save_for_best_ship:
            best_ship_to_buy = ship
            hours_to_save_for_best_ship = new_time
    return best_ship_to_buy


def is_shipyard_stale(client: SpaceTraders, shipyard_wp: Waypoint):
    sql = """select last_updated from shipyard_types where shipyard_symbol = %s"""
    resp = try_execute_select(client.db_client.connection, sql, (shipyard_wp.symbol,))
    if not resp:
        return True

    last_updated = resp[0][0]
    if last_updated < datetime.utcnow() - timedelta(hours=1):
        return True
    return False


def should_we_accept_contract(client: SpaceTraders, contract: Contract):
    deliverable_goods = [deliverable.symbol for deliverable in contract.deliverables]
    for dg in deliverable_goods:
        if "ORE" in dg:
            return True

    # get average and best price for deliverael
    total_value = contract.payment_completion + contract.payment_upfront
    total_cost = 0
    for deliverable in contract.deliverables:
        cost = get_prices_for(client, deliverable.symbol)
        if not cost:
            logging.warning(
                "Couldn't find a market for %s, I don't think we should accept this contract %s ",
                deliverable.symbol,
                contract.id,
            )
            return False
        total_cost += cost[0] * deliverable.units_required
    if total_cost < total_value:
        return True
    elif total_cost < total_value * 2:
        logging.warning(
            "This contract is borderline, %scr to earn %scr - up to you boss [%s]",
            total_cost,
            total_value,
            contract.id,
        )
        return False

    logging.warning("I don't think we should accept this contract %s", contract.id)

    return False


def get_prices_for(client: SpaceTraders, tradegood: str):
    connection = client.db_client.connection

    sql = """select * from market_prices where trade_symbol = %s"""
    rows = try_execute_select(connection, sql, (tradegood,))
    if rows:
        row = rows[0]
        average_price_buy = row[1]
        average_price_sell = row[2]
        return [average_price_buy, average_price_sell]
    return None


def process_contracts(client: SpaceTraders):
    contracts = client.view_my_contracts()
    need_to_negotiate = True
    for con in contracts.values():
        con: Contract
        should_we_complete = False

        if con.accepted and not con.fulfilled:
            should_we_complete = True

            need_to_negotiate = False
            for deliverable in con.deliverables:
                if deliverable.units_fulfilled < deliverable.units_required:
                    should_we_complete = False
        if should_we_complete:
            client.contracts_fulfill(con)

        if not con.accepted:
            need_to_negotiate = False
            if should_we_accept_contract(client, con):
                client.contract_accept(con.id)
    if need_to_negotiate:
        # get ships at the HQ, and have one do the thing
        ships = client.ships_view()
        satelite = [ship for ship in ships.values() if ship.role == "SATELLITE"][0]
        client.ship_negotiate(satelite)


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


def fleet_refresh_market_data(client: SpaceTraders):
    #
    # 0. Get all systems
    # 0. Get all jump gates
    # 1. pick an out-of-date location on the jump gate network to refresh

    pass


def maybe_buy_ship(client: SpaceTraders, connection, ship_symbol):
    """at the cheapest shipyard in the galaxy"""
    sql = """select ship_type, cheapest_location from shipyard_prices
        where ship_type = %s"""
    rows = try_execute_select(connection, sql, (ship_symbol,))
    if not rows:
        logger.error("Couldn't find ship type %s", ship_symbol)
        return False
    target_wp_sym = rows[0][1]
    print(f"attempting to buy {ship_symbol} at price from {target_wp_sym}")
    target_wp = client.waypoints_view_one(waypoint_slicer(target_wp_sym), target_wp_sym)
    shipyard = client.system_shipyard(target_wp)
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
    sql = "select distinct agent_name from ships"
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


def get_systems_to_explore(client: SpaceTraders, ships: list[Ship]):
    pass
    sql = """select distinct jump_gate_Waypoint, x,y,last_updated 
    from mkt_shpyrds_systems_last_updated_jumpgates
    order by last_updated asc 
    limit %s """
    results = try_execute_select(sql, client.db_client.connection, (len(ships),))
    return_obj = {ship.name: "" for ship in ships}
    for result in results:
        return_obj[results[0]] = (result[1], result[2])
    # limit ourselves to the 50 oldest waypoints.

    # for each potential waypoint targets figure out the age / distance
    # that way the older it is the more important it is. The closer it is, the more important it is for this given ship.


def is_market_data_stale(
    client: SpaceTraders, waypoint_sym: str, age_in_minutes: int = 60
):
    wp = client.waypoints_view_one(waypoint_slicer(waypoint_sym), waypoint_sym)
    market = client.system_market(wp)
    return market.is_stale()


def are_surveys_weak(client: SpaceTraders, asteroid_waypoint_symbol: str) -> bool:
    asteroid_wp = client.waypoints_view_one(
        waypoint_slicer(asteroid_waypoint_symbol), asteroid_waypoint_symbol
    )

    # determine value for each survey based on the market data.
    # asteroid should have a "max market value", which is the highest sell price possible
    # if the best survey is less than 50% of the max market value, surveys are weak.

    # survey has a value per market. We should calculate and store this with an expiration date died to the staleness of the data.
    #


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
