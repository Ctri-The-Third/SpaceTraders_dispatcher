from datetime import datetime, timedelta
import logging, math
import json
from time import sleep
from functools import partial

import psycopg2.sql


from straders_sdk.local_response import LocalSpaceTradersRespose
from straders_sdk.models import Shipyard, ShipyardShip, Waypoint, Agent, Market
from straders_sdk.ship import Ship
from straders_sdk.client_mediator import SpaceTradersMediatorClient as SpaceTraders
from straders_sdk.contracts import Contract
from straders_sdk.pathfinder import PathFinder
from straders_sdk.utils import (
    set_logging,
    waypoint_slicer,
    try_execute_select,
    try_execute_upsert,
)
from dispatcherWK16 import (
    BHVR_EXTRACT_AND_GO_SELL,
    BHVR_MONITOR_CHEAPEST_PRICE,
    BHVR_EXPLORE_SYSTEM,
    BHVR_EXTRACT_AND_TRANSFER,
    BHVR_CHILL_AND_SURVEY,
    BHVR_BUY_AND_DELIVER_OR_SELL,
    BHVR_REFUEL_ALL_IN_SYSTEM,
    BHVR_MONITOR_SPECIFIC_LOCATION,
    BHVR_TAKE_FROM_EXTRACTORS_AND_FULFILL,
    BHVR_SIPHON_AND_CHILL,
    BHVR_MANAGE_SPECIFIC_EXPORT,
    BHVR_CONSTRUCT_JUMP_GATE,
    BHVR_SELL_OR_JETTISON_ALL_CARGO,
    BHVR_CHAIN_TRADE,
    BHVR_EXECUTE_CONTRACTS,
    BHVR_EXTRACT_AND_CHILL,
)

from dispatcherWK16 import (
    RQ_ANY_FREIGHTER,
    RQ_CARGO,
    RQ_DRONE,
    RQ_EXPLORER,
    RQ_FUEL,
    RQ_HEAVY_FREIGHTER,
)
from behaviours.generic_behaviour import Behaviour as GenericBehaviour

from conductor_functions import (
    process_contracts,
    get_prices_for,
    set_behaviour,
    maybe_buy_ship_sys,
    log_task,
    log_shallow_trade_tasks,
    log_mining_package_deliveries,
    missing_market_prices,
    wait_until_reset,
)


logger = logging.getLogger(__name__)


# we should go through the markets available and manage exports for each of them.
# ship_parts and


class BehaviourConductor:

    """This behaviour manager is for when we're in low fuel desperate situations"""

    def __init__(self, user: dict[str, str], connection=None, session=None) -> None:
        self.current_agent_symbol = user.get("agents")[0]["username"]
        self.current_agent_token = user.get("agents")[0]["token"]

        client = self.st = SpaceTraders(
            self.current_agent_token,
            db_host=user["db_host"],
            db_port=user["db_port"],
            db_name=user["db_name"],
            db_user=user["db_user"],
            db_pass=user["db_pass"],
            current_agent_symbol=self.current_agent_symbol,
        )
        self.connection = client.db_client.connection
        self.asteroid_wps: list[Waypoint] = []
        self.haulers = []
        self.commanders = []
        self.hounds = []
        self.extractors = []
        self.surveyors = []
        self.ships_we_might_buy = ["SHIP_MINING_DRONE"]
        self.satellites = []
        self.refiners = []
        self.pathfinder = PathFinder(connection=self.connection)
        self.next_quarterly_update = None
        self.next_daily_update = None
        self.starting_system = None
        self.safety_margin = 0
        self.starting_planet = None

        self.gas_giant = None
        self.gas_exchange = None
        self.fuel_refinery = None

        self.tradegood_and_ship_mappings = {
            "SHIP_PARTS": None,
            "SHIP_PLATING": None,
            "ADVANCED_CIRCUITRY": None,
            "ELECTRONICS": None,
            "MICROPROCESSORS": None,
            "EXPLOSIVES": None,
            "COPPER": None,
        }

        # * progress missions
        hq = self.st.view_my_self().headquarters
        hq_sys = waypoint_slicer(hq)
        self.st.ships_view(True)

        self.starting_system = self.st.systems_view_one(hq_sys, True)
        self.starting_planet = self.st.waypoints_view_one(hq_sys, hq)
        for sym in self.starting_system.waypoints:
            wp = self.st.waypoints_view_one(self.starting_system.symbol, sym.symbol)
            if "MARKETPLACE" in [t.symbol for t in wp.traits]:
                self.st.system_market(wp)
            if "SHIPYARD" in [t.symbol for t in wp.traits]:
                self.st.system_shipyard(wp)
            if wp.type == "JUMP_GATE":
                self.st.system_jumpgate(wp)

    @property
    def max_cargo_available(self):
        max_cargo = 0
        for ship in self.commanders + self.haulers:
            if ship.cargo_capacity > max_cargo:
                return ship.cargo_capacity

    def run(self):
        #
        # * scale regularly and set defaults

        self.next_quarterly_update = datetime.now() + timedelta(minutes=15)
        self.next_hourly_update = datetime.now() + timedelta(hours=1)

        self.next_daily_update = datetime.now() + timedelta(days=1)
        #
        # hourly calculations of profitable things, assign behaviours and tasks
        #

        # rerun the hourly thing after we've calculated "ships we might buy"
        starting_run = True
        while True:
            logging.info("Conductor is running")
            self.populate_ships()
            # daily reset uncharted waypoints.
            # hourly set ship behaviours
            # quarterly set ship tasks
            # minutely try and buy new ships
            self.st.view_my_self()
            if self.next_daily_update < datetime.now():
                self.next_daily_update = datetime.now() + timedelta(days=1)
                self.daily_update()

            if self.next_hourly_update < datetime.now():
                self.next_hourly_update = datetime.now() + timedelta(hours=1)
                self.hourly_update()

            if self.next_quarterly_update < datetime.now():
                self.next_quarterly_update = datetime.now() + timedelta(minutes=15)
                self.quarterly_update()

            if starting_run:
                self.daily_update()
                self.hourly_update()
                self.quarterly_update()
                starting_run = False
            self.minutely_update()

            sleep(60)

    def daily_update(self):
        """Reset uncharted waypoints and refresh materialised views."""

        #
        # check for first run
        #
        if missing_market_prices(self.connection, self.starting_system.symbol):
            bhvr_params = {"target_sys": self.starting_system.symbol}
            log_task(
                self.connection,
                BHVR_EXPLORE_SYSTEM,
                [],
                self.starting_system.symbol,
                1,
                self.current_agent_symbol,
                bhvr_params,
                specific_ship_symbol=self.commanders[0].name,
            )

        self.gas_giant = self.st.find_waypoints_by_type_one(
            self.starting_system.symbol, "GAS_GIANT"
        )

        self.set_satellite_behaviours()
        self.set_siphoning()
        self.set_extraction_drones()

    def hourly_update(self):
        "Where the majority of ship behaviours should be set"

        if self.safety_margin == 0:
            self.safety_margin = 150000 * len(self.haulers + self.commanders)

        # just in case any behaviours have been terminated half way through and ships have stuff they don't know what to do with:
        for ship in self.commanders + self.haulers:
            log_task(
                self.connection,
                BHVR_SELL_OR_JETTISON_ALL_CARGO,
                [],
                ship.nav.system_symbol,
                5,
                self.current_agent_symbol,
                {},
                self.next_hourly_update,
                ship.name,
            )
        self.set_hauler_behaviours()
        # self.set_refinery_behaviours(possible_ships)
        self.set_satellite_behaviours()

    def quarterly_update(self):
        return

    def minutely_update(self):
        # for each engineered asteroid - position 20 extractors
        # for each asteroid with either an exchange or import within 80 clicks, deploy 10 extractors

        # if len(self.shuttles) < 5:
        #    maybe_buy_ship_sys(self.st, "SHIP_LIGHT_SHUTTLE", self.safety_margin)
        t = None

        coordinates = self.get_distinct_coordinates_with_marketplaces()
        types = self.get_distinct_ship_types()
        total_satellites_needed = len(coordinates) + len(types)
        if len(self.satellites) < total_satellites_needed:
            for i in range(total_satellites_needed - len(self.satellites)):
                t = maybe_buy_ship_sys(self.st, "SHIP_PROBE", self.safety_margin)
                if t:
                    self.satellites.append(t)
                if not t:
                    break
            if t:
                self.set_satellite_behaviours()
        if t:
            return

    def get_distinct_coordinates_with_marketplaces(self):
        market_places = self.st.find_waypoints_by_trait(
            self.starting_system.symbol, "MARKETPLACE"
        )
        if not market_places:
            return {}
        coordinates = {}

        coordinates = {(wp.x, wp.y): wp for wp in market_places}
        return coordinates

    def get_distinct_ship_types(self):
        ship_types_sql = """select distinct ship_type  from shipyard_types"""
        types = try_execute_select(self.connection, ship_types_sql, ())
        if not types:
            return []
        types = [t[0] for t in types]
        return types

    def set_extraction_drones(self):
        # see scale_and_set_siphoning
        # for siphoner in self.siphoners:
        #   set_behaviour(
        if len(self.extractors) == 0:
            return
        sites = self.get_mining_sites(
            self.starting_system.symbol, self.extractors[0].fuel_capacity
        )
        banned_sites = ["X1-PK16-B44"]
        allocated_drones = 0
        stop = False
        for site in sites:
            if stop:
                break
            system_symbol, extraction_waypoint, site_type, extractables, distance = site
            wayp = self.st.waypoints_view_one(system_symbol, extraction_waypoint)

            if site_type == "ENGINEERED_ASTEROID":
                needed_drones = 20
            else:
                needed_drones = 10
            params = {
                "asteroid_wp": extraction_waypoint,
                "cargo_to_transfer": extractables,
                "priority": 5,
            }
            if "UNSTABLE" in wayp.modifiers or extraction_waypoint in banned_sites:
                params["waypoint"] = extraction_waypoint
            for i in range(needed_drones):
                bhvr = BHVR_EXTRACT_AND_GO_SELL
                if "UNSTABLE" in wayp.modifiers or extraction_waypoint in banned_sites:
                    bhvr = BHVR_MONITOR_SPECIFIC_LOCATION
                elif needed_drones == 10 and i > 5:
                    bhvr = BHVR_EXTRACT_AND_CHILL

                if allocated_drones >= len(self.extractors):
                    stop = True
                    break

                extractor = self.extractors[allocated_drones]
                allocated_drones += 1
                params["delay_start"] = i * 10
                set_behaviour(self.connection, extractor.name, bhvr, params)

        return

    def set_satellite_behaviours(self):
        "ensures that each distinct celestial body (excluding moons etc...) has a satellite, and a shipyard for each ship"

        market_places = self.st.find_waypoints_by_trait(
            self.starting_system.symbol, "MARKETPLACE"
        )
        if not market_places:
            return
        coordinates = {}

        coordinates = {(wp.x, wp.y): wp for wp in market_places}
        ship_types_sql = """select distinct ship_type  from shipyard_types"""
        types = try_execute_select(self.connection, ship_types_sql, ())

        types = ["SHIP_PROBE", "SHIP_LIGHT_HAULER"]
        types = [t[0] for t in types]
        if "SHIP_PROBE" in types:
            types.remove("SHIP_PROBE")
            set_behaviour(
                self.connection,
                self.satellites[0].name,
                BHVR_MONITOR_CHEAPEST_PRICE,
                {"ship_type": "SHIP_PROBE"},
            )

        i = -1
        for satellite in self.satellites[1 : len(types) + 1]:
            try:
                i += 1
                set_behaviour(
                    self.connection,
                    satellite.name,
                    BHVR_MONITOR_CHEAPEST_PRICE,
                    {"ship_type": types[i]},
                )
            except:
                pass
        i = 0
        for satellite in self.satellites[len(types) + 1 :]:
            set_behaviour(
                self.connection,
                satellite.name,
                BHVR_MONITOR_SPECIFIC_LOCATION,
                {"waypoint": list(coordinates.values())[i].symbol},
            )
            i += 1

    def set_hauler_behaviours(self):
        # set the commander to chain trades.
        # we'll want to get a hauler to execute on contracts, but so far we don't know if contracts or chain trading is more effective.
        set_behaviour(self.connection, self.commanders[0].name, BHVR_CHAIN_TRADE, {})
        if len(self.haulers) > 0:
            set_behaviour(
                self.connection, self.haulers[0].name, BHVR_EXECUTE_CONTRACTS, {}
            )

        # at the end of the script, if all the target_tradegoods are being managed, build the jump gate.
        possible_ships = self.haulers[1:]

        # our goal is to get markets that we can manage.
        # however we can't guarantee that the markets will have imports and exports in the given system
        # this script goes through the list of tradegoods and their dependencies, and assigns a ship to each.
        target_tradegoods = [
            "EXPLOSIVES",
            "IRON",
            "COPPER",
            "ALUMINUM",
            "FUEL",
        ]
        tradesymbols_and_sources = None
        #  this code extends the tradegoods to find their dependencies - currently disabled
        for tradegood in target_tradegoods:
            tradesymbols_and_sources = map_tradesymbols_to_export_markets(
                self.connection,
                tradegood,
                self.starting_system.symbol,
                tradesymbols_and_sources,
            )

        if not tradesymbols_and_sources:
            return
        targets = [
            (tradegood, source[0])
            for tradegood, source in tradesymbols_and_sources.items()
        ]
        index = 0
        for h in possible_ships:
            if len(targets) > index:
                tradegood, source = targets[index]
                if source == "EXTRACTABLE":
                    params = {"cargo_to_receive": [tradegood], "priority": 4}
                    set_behaviour(
                        self.connection,
                        h.name,
                        BHVR_TAKE_FROM_EXTRACTORS_AND_FULFILL,
                        params,
                    )
                else:
                    params = {
                        "target_tradegood": tradegood,
                        "market_wp": source,
                        "priority": 4,
                    }
                    set_behaviour(
                        self.connection,
                        h.name,
                        BHVR_MANAGE_SPECIFIC_EXPORT,
                        params,
                    )

            else:
                # this needs to be context aware.
                set_behaviour(self.connection, h.name, BHVR_CONSTRUCT_JUMP_GATE, {})
            index += 1

    def set_refinery_behaviours(self, possible_ships):
        #
        # we can't guarantee a HYDROCARBON EXPORT anymore, and in fact it's going to be an EXTRACTOR instead.
        #

        pass

    def set_siphoning(self):
        # should be a quarterly or hourly behaviour

        if self.gas_giant:
            # is there a place we can sell stuff orbiting the gas giant?
            # if so, extract_and_sell, else siphon_and_chill
            # if we don't constraint it this way, we might end up with 8hr drifts again
            bhvr = (
                BHVR_SIPHON_AND_CHILL
                if not self.gas_exchange
                else BHVR_EXTRACT_AND_GO_SELL
            )
            params = {
                "asteroid_wp": self.gas_giant.symbol,
                "cargo_to_transfer": ["*"],
            }
            if self.gas_exchange:
                params["market_wp"] = self.gas_exchange.symbol
            for s in self.siphoners:
                set_behaviour(self.connection, s.name, bhvr, params)

    def find_unassigned_ships(self) -> list[Ship]:
        symbols = self.find_unassigned_ship_symbols()
        return [self.st.ships_view_one(s) for s in symbols]

    def find_unassigned_ship_symbols(self) -> list[str]:
        sql = """select ship_symbol from ship_behaviours 
        where behaviour_id is null
        and ship_symbol ilike %s"""

        results = try_execute_select(
            self.connection, sql, (f"{self.current_agent_symbol}-%",)
        )
        return [r[0] for r in results]

    def find_hydrocarbon_exporter(self) -> Market:
        pass

    def find_fuel_refineries(self, relative_to: Waypoint = None) -> Waypoint:
        sql = """select system_symbol, waypoint_symbol, type,  x, y
        from refinery_fuel where system_symbol = %s"""
        results = try_execute_select(
            self.connection, sql, (self.starting_system.symbol,)
        )
        if not results:
            return None
        closest_distance = float("inf")
        closest_refinery = None
        relative_to = relative_to or Waypoint(
            "", "", "", 0, 0, [], [], {}, {}, [], False
        )

        for refinery in results:
            wp = Waypoint(*refinery, [], [], {}, {})
            d = self.pathfinder.calc_distance_between(relative_to, wp)
            if d < closest_distance:
                closest_distance = d
                closest_refinery = wp

        return closest_refinery

    def any_refuels_needed(self, fuel_levels=("LIMITED", "SCARCE")):
        waypoints = self.st.find_waypoints_by_trait(
            self.starting_system.symbol, "MARKETPLACE"
        )
        markets = [self.st.system_market(wp) for wp in waypoints]
        for market in markets:
            fuel = market.get_tradegood("FUEL")
            if fuel and fuel.type == "EXCHANGE" and fuel.supply in fuel_levels:
                return True
        return False

    def maybe_upgrade_ship(self):
        # surveyors first, then extractors
        return False
        max_mining_strength = 60
        max_survey_strength = self.max_survey_strength() * 3
        best_surveyor = (
            "MOUNT_SURVEYOR_II" if max_survey_strength == 6 else "MOUNT_SURVEYOR_I"
        )
        if not clear_to_upgrade(self.st.view_my_self(), self.connection):
            return
        ship_to_upgrade = None
        ship_new_behaviour = None
        prices = get_prices_for(self.connection, best_surveyor)
        if not prices or len(prices) == 0:
            return
        price = prices[0] * 3
        if price is not None:
            for ship in self.surveyors:
                ship: Ship
                if ship.survey_strength < max_survey_strength:
                    outfit_symbols = [best_surveyor, best_surveyor, best_surveyor]
                    ship_to_upgrade = ship
                    switch_to_surveying(self.connection, ship_to_upgrade.name)
                    break

        if not ship_to_upgrade:
            for ship in self.extractors:
                ship: Ship
                if ship.extract_strength < max_mining_strength:
                    outfit_symbols = [
                        "MOUNT_MINING_LASER_II",
                        "MOUNT_MINING_LASER_II",
                        "MOUNT_MINING_LASER_I",
                    ]
                    ship_to_upgrade = ship

                    break
        if not ship_to_upgrade:
            return

        params = {"mounts": outfit_symbols}
        if self.st.view_my_self().credits < price:
            return
        log_task(
            self.connection,
            "UPGRADE_TO_SPEC",
            [],
            ship_to_upgrade.nav.system_symbol,
            1,
            self.st.current_agent_symbol,
            params,
            specific_ship_symbol=ship_to_upgrade.name,
            expiry=self.next_quarterly_update,
        )

    def max_mining_strength(self):
        sql = """select * from market_prices
where trade_symbol ilike 'mount_mining_laser%'"""
        results = try_execute_select(self.connection, sql, ())
        symbols = [row[0] for row in results]
        if "MOUNT_MINING_LASER_II" in symbols:
            return 25
        elif "MOUNT_MINING_LASER_I" in symbols:
            return 10

    def max_survey_strength(self):
        sql = """select * from market_prices
where trade_symbol ilike 'mount_surveyor_%%'"""
        results = try_execute_select(self.connection, sql, [])
        symbols = [row[0] for row in results]
        if "MOUNT_SURVEYOR_II" in symbols:
            return 2
        elif "MOUNT_SURVEYOR_I" in symbols:
            return 1
        else:
            return 0

    def populate_ships(self):
        "Set the conductor's ship lists, and subdivides them into roles."
        ships = list(self.st.ships_view().values())
        ships.sort(key=lambda ship: ship.index)
        self.satellites = [ship for ship in ships if ship.role == "SATELLITE"]
        self.haulers = [ship for ship in ships if ship.role in ("HAULER")]
        self.shuttles = [ship for ship in ships if ship.role == "TRANSPORT"]
        self.commanders = [ship for ship in ships if ship.role == "COMMAND"]
        self.hounds = [ship for ship in ships if ship.frame.symbol == "FRAME_MINER"]
        self.extractors = [
            ship for ship in ships if ship.role == "EXCAVATOR" and ship.can_extract
        ]
        self.refiners = [ship for ship in ships if ship.role == "REFINERY"]
        self.surveyors = [ship for ship in ships if ship.role == "SURVEYOR"]
        self.siphoners = [
            ship for ship in ships if ship.role == "EXCAVATOR" and ship.can_siphon
        ]

    def log_tasks_for_contracts(self):
        contracts = self.st.view_my_contracts()
        unfulfilled_contracts = [
            con
            for con in contracts
            if not con.fulfilled and con.accepted and not con.is_expired
        ]
        # we   need to check we've enough money to fulfil the contract.
        tasks_logged = 0
        for con in unfulfilled_contracts:
            con: Contract
            tasks_logged = 0
            for deliverable in con.deliverables:
                remaining_to_deliver = (
                    deliverable.units_required - deliverable.units_fulfilled
                )
                deliverable_cost = self.get_market_prices_for(deliverable.symbol)
                if not deliverable_cost:
                    continue
                total_cost = (
                    deliverable_cost[1] or deliverable_cost[3]
                ) * remaining_to_deliver
                if self.st.current_agent.credits < total_cost + self.safety_margin:
                    continue
                for i in range(
                    math.ceil((remaining_to_deliver) / self.max_cargo_available)
                ):
                    log_task(
                        self.connection,
                        BHVR_BUY_AND_DELIVER_OR_SELL,
                        [RQ_ANY_FREIGHTER, f"{self.max_cargo_available}{RQ_CARGO}"],
                        waypoint_slicer(deliverable.destination_symbol),
                        3.9 - (i * 0.1),
                        self.current_agent_symbol,
                        {
                            "priority": 4,
                            "tradegood": deliverable.symbol,
                            "quantity": min(
                                remaining_to_deliver, self.max_cargo_available
                            ),
                            "fulfil_wp": deliverable.destination_symbol,
                        },
                        expiry=self.next_quarterly_update,
                    )
                    tasks_logged += 1
                    remaining_to_deliver -= self.max_cargo_available
        self.st.logger.info(f"Logged {tasks_logged} tasks for contracts")

    def get_market_prices_for(self, tradegood: str) -> tuple:
        sql = """select trade_symbol, export_price, import_price, galactic_average from market_prices
        where trade_symbol = %s"""
        results = try_execute_select(self.connection, sql, (tradegood,))
        if not results:
            return None
        return results[0]

    def get_trade_routes(
        self, limit=None, min_market_depth=100, max_market_depth=1000000
    ) -> list[tuple]:
        if not limit:
            limit = len(self.haulers)
        sql = """select route_value, system_symbol, trade_symbol, profit_per_unit, export_market, import_market, market_depth
        from trade_routes_intrasystem tris
        where market_depth >= %s
        and market_depth <= %s
        and system_symbol = %s
        limit %s"""
        routes = try_execute_select(
            self.connection,
            sql,
            (min_market_depth, max_market_depth, self.starting_system.symbol, limit),
        )
        if not routes:
            return []

        return [(r[2], r[4], r[5], r[3], r[1]) for r in routes]

    def get_mining_sites(self, system_sym: str, distance=80) -> list[tuple]:
        sql = """with unpacked_sites as (
            select system_Symbol,  unnest (array_agg) as extractable, extraction_waypoint, distance from mining_sites_and_exchanges
            where system_Symbol = %s
            and distance <= %s
	    )
	select us.system_symbol,  extraction_Waypoint, type, array_agg(extractable) as extractables, min(distance) 
	from unpacked_sites us
	join waypoints w on extraction_waypoint = w.waypoint_symbol
	group by 1,2,3
	order by 5 asc"""
        routes = try_execute_select(
            self.connection,
            sql,
            (system_sym, distance),
        )
        if not routes:
            return []
        return routes


def clear_to_upgrade(agent: Agent, connection) -> bool:
    """checks whether or not there's an open upgrade task.
    If the agent has more than a million credits, this will always return true."""
    if agent.credits >= 1000000:
        return True

    sql = """select * from ship_tasks
where behaviour_id = 'UPGRADE_TO_SPEC' and (not completed or completed is null)
and expiry > now() 
and agent_symbol = %s"""
    rows = try_execute_select(connection, sql, (agent.symbol,))
    return len(rows) == 0


def switch_to_surveying(connection, ship_symbol):
    sql = """update ship_behaviours set behaviour_id = %s where ship_symbol = %s"""
    try_execute_upsert(connection, sql, (BHVR_CHILL_AND_SURVEY, ship_symbol))


def map_tradesymbols_to_export_markets(
    connection,
    tradegood: str,
    system_symbol: str,
    managed_exports_and_markets: dict = None,
):
    if managed_exports_and_markets is None:
        managed_exports_and_markets = {}
    from straders_sdk.constants import EXTRACTABLES, SHIPONABLES

    sql = """with unnested_relationships as (
  select export_tradegood, unnest(import_tradegoods) as required_import from manufacture_relationships mr
  where export_tradegood = %s 
)
select mr.export_tradegood, w.waypoint_symbol, mr.required_import from unnested_Relationships mr
left join market_tradegood mt on mr.export_tradegood = mt.symbol 
left join waypoints w on mt.market_waypoint = w.waypoint_symbol
where (w.waypoint_symbol is null or ( buy_or_sell = 'sell'
and w.system_symbol = %s))"""

    results = try_execute_select(connection, sql, (tradegood, system_symbol))
    if not results:
        # check if the the export is actually an extractable
        if tradegood in EXTRACTABLES or tradegood in SHIPONABLES:
            managed_exports_and_markets[tradegood] = ["EXTRACTABLE"]
        for key, value in managed_exports_and_markets.items():
            # remove duplicates in value
            managed_exports_and_markets[key] = list(set(value))
        return managed_exports_and_markets

    for export_tradegood, export_market_wp, required_import in results:
        if export_tradegood not in managed_exports_and_markets:
            managed_exports_and_markets[export_tradegood] = []
        managed_exports_and_markets[export_tradegood].append(export_market_wp)

        # to re-enable recursion, uncomment the below
        # map_all_goods(
        #    connection, required_import, system_symbol, managed_exports_and_markets
        # )
    return managed_exports_and_markets
    # find markets that EXPORT the given tradegood
    # add them into managed_markets THEN determine the matching imports and manage each of those markets.


if __name__ == "__main__":
    set_logging()
    user = json.load(open("user.json"))
    had_to_wait = wait_until_reset("https://api.spacetraders.io/v2/", user)
    sleep(30 if had_to_wait else 0)
    user = json.load(open("user.json"))
    logger.info("Starting up conductor, preparing to connect to database")
    logger.info("Connected to database")
    agents = []
    agents_and_clients: dict[str:SpaceTraders] = {}

    #    `tradegood`: the symbol of the tradegood to buy\n
    # optional:\n
    # `buy_wp`: if you want to specify a source market, provide the symbol.\n
    # `sell_wp`: if you want the ship to sell the cargo, set which waypoint\n

    # `max_buy_price`: if you want to limit the purchase price, set it here\n
    # `min_sell_price`: if you want to limit the sell price, set it here\n
    conductor = BehaviourConductor(user)

    conductor.populate_ships()

    # goods.update(map_all_goods(conductor.connection, "SHIP_PLATING", "X1-YG29"))
    # for each tradegood we need a shuttle.
    # for each tradegood either manage the export, or go collect from extractors.

    # we also need to manually manage FUEL and EXPLOSIVES
    conductor.run()
