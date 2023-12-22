from straders_sdk import SpaceTraders
from straders_sdk.contracts import Contract
from straders_sdk.utils import (
    try_execute_select,
    try_execute_upsert,
    waypoint_slicer,
    get_and_validate,
)
from straders_sdk.local_response import LocalSpaceTradersRespose
from straders_sdk.models import System

import datetime
import logging
import json
import hashlib
import time


def process_contracts(client: SpaceTraders, recurse=True):
    contracts = client.view_my_contracts()
    need_to_negotiate = True

    open_contracts = [
        con for con in contracts if not con.fulfilled and not con.is_expired
    ]

    for con in open_contracts:
        con: Contract
        should_we_complete = False

        if con.accepted and not con.fulfilled and not con.is_expired:
            should_we_complete = True

            need_to_negotiate = False
            for deliverable in con.deliverables:
                if deliverable.units_fulfilled < deliverable.units_required:
                    should_we_complete = False
        if should_we_complete:
            client.contracts_fulfill(con)
            need_to_negotiate = True

        if not con.accepted and con.deadline_to_accept > datetime.datetime.utcnow():
            need_to_negotiate = False
            if should_we_accept_contract(client, con):
                client.contract_accept(con.id)
    if need_to_negotiate:
        # get ships at the HQ, and have one do the thing
        ships = client.ships_view()
        satelite = [ship for ship in ships.values() if ship.role == "SATELLITE"][0]
        resp = client.ship_negotiate(satelite)
        if resp and recurse:
            logging.info("Negotiated a contract %s", resp)
            process_contracts(client, False)


def should_we_accept_contract(client: SpaceTraders, contract: Contract):
    deliverable_goods = [deliverable.symbol for deliverable in contract.deliverables]
    for dg in deliverable_goods:
        if "ORE" in dg:
            return True

    # get average and best price for deliverael
    total_value = contract.payment_completion + contract.payment_upfront
    total_cost = 0
    for deliverable in contract.deliverables:
        cost = get_prices_for(client.db_client.connection, deliverable.symbol)
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


def wait_until_reset(url, user_file: dict):
    target_date = user_file["reset_date"]
    current_reset_date = "1990-01-01"
    had_to_wait = False
    while target_date != current_reset_date:
        response = get_and_validate(url)
        try:
            if (
                response.status_code == 200
                and response.response_json["resetDate"] == target_date
            ):
                return had_to_wait
            elif response.status_code == 200:
                current_reset_date = response.response_json["resetDate"]
                logging.info(
                    "Reset date is %s - waiting for %s", current_reset_date, target_date
                )
            else:
                logging.info("It's coming!")
        except Exception as err:
            logging.error("Error %s", err)
        finally:
            had_to_wait = True
            time.sleep(5)


def get_prices_for(connection, tradegood: str, agent_symbol="@"):
    sql = """select mp.trade_Symbol, coalesce(export_price, galactic_average) as export_price, coalesce(import_price, galactic_average) as import_price from market_prices mp 
where mp.trade_Symbol = %s

"""
    rows = try_execute_select(connection, sql, (tradegood,))
    if rows and len(rows) > 0:
        row = rows[0]
        average_price_buy = row[1]
        average_price_sell = row[2]
        return [
            int(average_price_buy) if average_price_buy else None,
            int(average_price_sell) if average_price_sell else None,
        ]
    return []


def set_behaviour(connection, ship_symbol, behaviour_id, behaviour_params=None):
    sql = """INSERT INTO ship_behaviours (ship_symbol, behaviour_id, behaviour_params)
    VALUES (%s, %s, %s)
    ON CONFLICT (ship_symbol) DO UPDATE SET
        behaviour_id = %s,
        behaviour_params = %s
    """

    behaviour_params_s = (
        json.dumps(behaviour_params) if behaviour_params is not None else None
    )

    return try_execute_upsert(
        connection,
        sql,
        (
            ship_symbol,
            behaviour_id,
            behaviour_params_s,
            behaviour_id,
            behaviour_params_s,
        ),
    )


def missing_market_prices(
    connection, system_symbol: str, oldest_hours: int = 3
) -> bool:
    "helpful during first setup"

    sql = """with info as ( 
select mt.market_waypoint, count(mtl.market_symbol) as found_listings, min(mtl.last_updated) as last_updated from market_tradegood mt 
left join market_tradegood_listings mtl on mt.market_Waypoint = mtl.market_symbol and mt.symbol = mtl.trade_symbol
join waypoints w on mt.market_waypoint = w.waypoint_symbol
where system_symbol = %s
group by mt.market_waypoint

	)
	select * from info
	where last_updated < now() - interval '3 hours' or found_listings =  0"""
    results = try_execute_select(connection, sql, (system_symbol,))
    return len(results) > 0


def log_task(
    connection,
    behaviour_id: str,
    requirements: list,
    target_system: str,
    priority=5,
    agent_symbol=None,
    behaviour_params=None,
    expiry: datetime = None,
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
    on conflict(task_hash) DO UPDATE set completed = False 
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

    return hash_str if resp else resp


def maybe_buy_ship_sys(
    client: SpaceTraders, ship_symbol, safety_margin: int = 0
) -> "Ship" or None:
    location_sql = """select distinct shipyard_symbol, ship_cost from shipyard_types st 
join ship_nav sn on  st.shipyard_symbol = sn.waypoint_symbol
join ships s on s.ship_symbol = sn.ship_symbol
where s.agent_name = %s
and st.ship_type = %s
order by ship_cost desc """
    rows = try_execute_select(
        client.db_client.connection,
        location_sql,
        (client.current_agent_symbol, ship_symbol),
    )
    if len(rows) == 0:
        logging.warning(f"Tried to buy a ship {ship_symbol} but couldn't find one")
        return False
    best_waypoint = rows[0][0]

    wayp = client.waypoints_view_one(waypoint_slicer(best_waypoint), best_waypoint)
    shipyard = client.system_shipyard(wayp)
    return _maybe_buy_ship(client, shipyard, ship_symbol, safety_margin)


def _maybe_buy_ship(
    client: SpaceTraders, shipyard: "Shipyard", ship_symbol: str, safety_margin: int = 0
):
    agent = client.view_my_self()

    if not shipyard:
        logging.warning(
            f"Tried to buy a ship {ship_symbol} but couldn't find a shipyard"
        )
        return False
    for _, detail in shipyard.ships.items():
        detail: "ShipyardShip"
        if detail.ship_type == ship_symbol:
            if not detail.purchase_price:
                return LocalSpaceTradersRespose(
                    f"We don't have price information for this shipyard. {shipyard.waypoint}",
                    0,
                    0,
                    "conductorWK7.maybe_buy_ship",
                )
            if agent.credits > (detail.purchase_price + safety_margin):
                resp = client.ships_purchase(ship_symbol, shipyard.waypoint)
                if resp:
                    return resp[0]
            else:
                logging.warning(
                    f"Tried to buy a ship {ship_symbol} but didn't have enough credits ({agent.credits}))"
                )
                return False


def register_and_store_user(
    username, logger=logging.getLogger("Conductor_functions")
) -> str:
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


def find_best_market_systems_to_sell(
    connection, trade_symbol: str
) -> list[(str, System, int)]:
    "returns market_waypoint, system obj, price as int"
    sql = """select sell_price, w.waypoint_symbol, s.system_symbol, s.sector_Symbol, s.type, s.x,s.y from market_tradegood_listings mtl 
join waypoints w on mtl.market_symbol = w.waypoint_Symbol
join systems s on w.system_symbol = s.system_symbol
where mtl.trade_symbol = %s
order by 1 desc """
    results = try_execute_select(connection, sql, (trade_symbol,))
    return_obj = []
    for row in results or []:
        sys = System(row[2], row[3], row[4], row[5], row[6], [])
        price = row[0]
        waypoint_symbol = row[1]
        return_obj.append((waypoint_symbol, sys, price))
    return return_obj


def log_mining_package_deliveries(
    connection,
    collection_task_id: str,
    current_agent_symbol: str,
    current_system_symbol: str,
    task_expiry: datetime.datetime,
):
    sql = """
with potentials as (
	select ROW_NUMBER() OVER (PARTITION BY tecp.source_waypoint ORDER BY package_value desc) AS row_number
	, 
	*
	, (package_value / greatest(distance,1) )as cph 
	from trade_extraction_packages tecp
	where source_waypoint ilike %s and 
			market_symbol ilike %s 					
	order by package_value / greatest(distance,1) 
) 

select trade_symbols, source_waypoint,market_symbol, package_value, distance from potentials where row_number = 1

order by package_value/greatest(distance,1) desc;"""
    rows = try_execute_select(
        connection, sql, (f"{current_system_symbol}%", f"{current_system_symbol}%")
    )
    for row in rows:
        trade_symbols, source_waypoint, market_symbol, package_value, distance = row
        task_id = log_task(
            connection,
            collection_task_id,
            ["40_CARGO", "ANY_FREIGHTER"],
            waypoint_slicer(market_symbol),
            4 + 1 / (package_value / 40),
            current_agent_symbol,
            {
                "asteroid_wp": source_waypoint,
                "cargo_to_receive": trade_symbols,
                "market_wp": market_symbol,
                "priority": 3.9,
            },
            expiry=task_expiry,
        )


def log_shallow_trade_tasks(
    connection,
    credits_available: int,
    trade_task_id: str,
    current_agent_symbol: str,
    task_expiry: datetime.datetime,
    max_tasks: int,
    target_system: str,
) -> int:
    capital_reserve = 0
    routes = get_99pct_shallow_trades(
        connection,
        credits_available,
        target_system,
        limit=max_tasks,
    )
    if len(routes) == 0:
        logging.warning(
            f"No optimum shallow trades found {credits_available} cr, limit of {max_tasks}"
        )
        routes = get_abundant_scarce_trades(
            connection,
            credits_available,
            target_system,
            limit=max_tasks,
        )
    if len(routes) == 0:
        logging.warning(
            f"No abundant scarce trades found {credits_available} cr, limit of {max_tasks}"
        )
        return 0
    for route in routes:
        (
            trade_symbol,
            export_market,
            import_market,
            profit_per_unit,
            cost_to_execute,
            min_market_depth,
        ) = route
        capital_reserve += cost_to_execute
        task_id = log_task(
            connection,
            trade_task_id,
            ["ANY_FREIGHTER"],
            waypoint_slicer(import_market),
            4 + (1 / profit_per_unit),
            current_agent_symbol,
            {
                "buy_wp": export_market,
                "sell_wp": import_market,
                "tradegood": trade_symbol,
                "safety_profit_threshold": profit_per_unit / 2,
                "priority": 4.5,
                "quantity": min_market_depth,
            },
            expiry=task_expiry,
        )
        logging.info(
            f"logged a shallow trade task {trade_symbol} {export_market}->{import_market} | {profit_per_unit * 35} profit | for {cost_to_execute} cr - {task_id}"
        )

    return capital_reserve


def get_imports_for_export(
    connection,
    trade_symbol: str,
    export_waypoint: str,
    specific_system: str = None,
) -> list[tuple]:
    sql = """select tri.trade_symbol, system_symbol, export_market, import_market, market_depth
    where (case when %s is not True then specific_system = %s else True end)
    and (case when %s is not True then trade_symbol = %s else True end) 
    and (case when %s is not True then export_system = %s else True end) """

    results = try_execute_select(
        connection,
        sql,
        (
            specific_system is not None,
            specific_system,
            trade_symbol is not None,
            trade_symbol,
            export_waypoint is not None,
            export_waypoint,
        ),
    )
    return results


def get_99pct_shallow_trades(
    connection, working_capital: int, target_system_symbol: str, limit=50
) -> list[tuple]:
    sql = """select tri.trade_symbol, system_symbol, profit_per_unit, export_market, import_market, market_depth, purchase_price * market_depth
    from trade_routes_intrasystem tri 
    left join trade_routes_max_potentials trmp on tri.trade_symbol =  trmp.trade_symbol
    where market_depth <= 80 and (purchase_price * market_depth) < %s
    and system_symbol = %s
	and  ( case when trmp.trade_symbol is not null then round((sell_price::numeric/ purchase_price)*100,2) > profit_pct *0.99 else True end ) 
	order by route_value desc
    limit %s"""

    routes = try_execute_select(
        connection,
        sql,
        (
            working_capital,
            target_system_symbol,
            limit,
        ),
    )
    if not routes:
        return []
    return [(r[0], r[3], r[4], r[2], r[6], r[5]) for r in routes]


def get_abundant_scarce_trades(
    connection, working_capital: int, target_system_symbol: str, limit=50
) -> list[tuple]:
    sql = """select trade_symbol, system_symbol, profit_per_unit, export_market, import_market,  market_depth, purchase_price * market_depth
    from trade_routes_intrasystem tri 
    where market_depth <= 80 and (purchase_price * market_depth) < %s
    and system_symbol = %s
    and supply_text = 'ABUNDANT' and import_supply = 'SCARCE' 
    order by route_value desc
    limit %s"""

    routes = try_execute_select(
        connection,
        sql,
        (
            working_capital,
            target_system_symbol,
            limit,
        ),
    )
    if not routes:
        return []
    return [(r[0], r[3], r[4], r[2], r[6], r[5]) for r in routes]


"""

ineries exist where the planet exports a given resource. 
if we want to grow a refinery we need to export it.

routes are links between refineries.

"""
