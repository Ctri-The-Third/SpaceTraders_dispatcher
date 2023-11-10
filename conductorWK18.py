"""
Strategy for week 18 

## behaviours to manage
# siphon and transfer
# refuel in system
# stable trades
# extract and transfer
# drip-feed trades

## ships to scale to
# command
# 2 haulers
# siphon fleet
# extractor fleet + transfer

"""

from datetime import datetime, timedelta
import logging
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
    BHVR_RECEIVE_AND_FULFILL,
    BHVR_RECEIVE_AND_REFINE,
    BHVR_REMOTE_SCAN_AND_SURV,
    BHVR_MONITOR_CHEAPEST_PRICE,
    BHVR_EXPLORE_SYSTEM,
    BHVR_EXTRACT_AND_TRANSFER,
    BHVR_CHILL_AND_SURVEY,
    BHVR_BUY_AND_DELIVER_OR_SELL,
    BHVR_REFUEL_ALL_IN_SYSTEM,
    BHVR_SINGLE_STABLE_TRADE,
)
from behaviours.generic_behaviour import Behaviour as GenericBehaviour

from conductor_functions import (
    process_contracts,
    get_prices_for,
    set_behaviour,
    maybe_buy_ship_sys,
    log_task,
    log_shallow_trade_tasks,
)


logger = logging.getLogger(__name__)


class FuelManagementConductor:

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

    def run(self):
        #
        # * scale regularly and set defaults
        # * progress missions
        hq = self.st.view_my_self().headquarters
        hq_sys = waypoint_slicer(hq)
        self.starting_system = self.st.systems_view_one(hq_sys)
        self.starting_planet = self.st.waypoints_view_one(hq_sys, hq)

        self.next_quarterly_update = datetime.now() + timedelta(minutes=15)
        last_quarterly_update = datetime.now() - timedelta(minutes=30)
        last_daily_update = datetime.now() - timedelta(days=2)
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

            if self.next_daily_update < datetime.now():
                self.next_daily_update = datetime.now() + timedelta(days=1)
                self.daily_update()
                last_daily_update = datetime.now()

            if self.next_quarterly_update < datetime.now():
                self.next_quarterly_update = datetime.now() + timedelta(minutes=15)
                self.quarterly_update()

            self.minutely_update()
            if starting_run:
                self.daily_update()
                self.quarterly_update()
                starting_run = False
            sleep(60)

    def daily_update(self):
        # here's the priority of behaviours (not tasks)

        possible_ships = self.haulers + self.commanders
        self.gas_giant = gas_giant = self.st.find_waypoints_by_type_one(
            self.starting_system.symbol, "GAS_GIANT"
        )
        self.fuel_refinery = fuel_refinery = self.find_fuel_refineries(gas_giant)
        hydrocarbon_shipper = possible_ships[0]

        # set behaviour - hydrocarbon shipper siphons hydrocarbon from export and sells to fuel refinery
        # if we have a fuel shipper,  it all the fuel shipping tasks possible
        if len(self.haulers) >= 2:
            for h in possible_ships[2:]:
                set_behaviour(self.connection, h.name, BHVR_SINGLE_STABLE_TRADE, {})
            # spare haulers all get told to trade tasks
            # ander gets set on siphoner duty
        #
        # daily recon task
        #

    def quarterly_update(self):
        # if we have a fuel shipper, give it all the fuel shipping tasks possible
        # if not, give the exporter a refuel task for 1 (maybe 2) points.
        self.safety_margin = 0

        possible_ships = self.haulers + self.commanders
        self.set_refinery_behaviours(possible_ships)

        if len(self.haulers) > 2:
            log_shallow_trade_tasks(
                self.connection,
                self.st.view_my_self().credits,
                BHVR_BUY_AND_DELIVER_OR_SELL,
                self.current_agent_symbol,
                self.next_quarterly_update,
                len(self.haulers) - 2,
            )

    def minutely_update(self):
        if len(self.haulers) < 5:
            maybe_buy_ship_sys(self.st, "SHIP_LIGHT_HAULER", self.safety_margin)
        pass

        for s in self.find_unassigned_ships():
            if s.role == "SATELLITE":
                set_behaviour(self.connection, s.name, BHVR_REMOTE_SCAN_AND_SURV, {})
            elif s.role == "EXCAVATOR":
                set_behaviour(self.connection, s.name, BHVR_EXTRACT_AND_TRANSFER, {})
            elif s.role == "SURVEYOR":
                set_behaviour(self.connection, s.name, BHVR_CHILL_AND_SURVEY, {})
            elif s.role == "REFINERY":
                set_behaviour(self.connection, s.name, BHVR_RECEIVE_AND_REFINE, {})
            elif s.role == "HAULER":
                set_behaviour(self.connection, s.name, BHVR_SINGLE_STABLE_TRADE, {})
            elif s.role == "COMMAND":
                set_behaviour(self.connection, s.name, BHVR_EXPLORE_SYSTEM, {})

    def set_refinery_behaviours(self, possible_ships):
        hydrocarbon_shipper = possible_ships[0]
        hydrocarbon_shipper: Ship
        refueler = possible_ships[min(1, len(possible_ships) - 1)]

        fuel_refinery = self.st.system_market(self.fuel_refinery)
        cargo_requirement = 35 if len(self.haulers) > 0 else 70
        fuel = fuel_refinery.get_tradegood("FUEL")

        # if we've enough fuel , send a refuel task, otherwise log a shallow trade
        log_trade = False
        if fuel.supply in ("ABUNDANT", "HIGH"):
            if self.any_refuels_needed():
                log_task(
                    self.connection,
                    BHVR_REFUEL_ALL_IN_SYSTEM,
                    [f"{cargo_requirement}_CARGO"],
                    waypoint_slicer(self.gas_giant.symbol),
                    4,
                    self.current_agent_symbol,
                    {},
                    expiry=self.next_quarterly_update,
                    specific_ship_symbol=refueler.name,
                )
            else:
                log_trade = True
                trades_to_log = 5
        else:
            log_trade = True
            trades_to_log = 1

        if log_trade:
            log_shallow_trade_tasks(
                self.connection,
                self.st.view_my_self().credits,
                BHVR_BUY_AND_DELIVER_OR_SELL,
                self.current_agent_symbol,
                self.next_quarterly_update,
                trades_to_log,
            )

        # either use the commander or a spare hauler to receive siphoned stuff and sell it. Commander has the advantage of extracting it too.
        set_behaviour(
            self.connection,
            hydrocarbon_shipper.name,
            BHVR_EXTRACT_AND_GO_SELL
            if hydrocarbon_shipper.role == "COMMAND"
            else BHVR_RECEIVE_AND_FULFILL,
            {"asteroid_wp": self.gas_giant.symbol, "market_wp": fuel_refinery.symbol},
        )

        set_behaviour(
            self.connection,
            self.satellites[0].name,
            BHVR_MONITOR_CHEAPEST_PRICE,
            {"ship_type": "SHIP_LIGHT_FREIGHTER"},
        )
        if len(possible_ships) > 1:
            fuel_shipper = possible_ships[1]
            set_behaviour(
                self.connection, fuel_shipper.name, BHVR_REFUEL_ALL_IN_SYSTEM, {}
            )

    def scale_and_set_siphoning(self, possible_ships):
        # should be a quarterly or hourly behaviour
        if len(possible_ships) > 2:
            command_role = BHVR_EXTRACT_AND_TRANSFER
        else:
            command_role = BHVR_EXTRACT_AND_GO_SELL

        if len(self.siphoners <= 10):
            ship = maybe_buy_ship_sys(self.st, "SHIP_SIPHON_DRONE", self.safety_margin)
            if ship:
                self.siphoners.append(ship)
            set_behaviour(
                self.connection,
                self.commanders[0].name,
                command_role,
                {"asteroid_wp": self.gas_giant, "cargo_to_transfer": ["*"]},
            )
        for s in self.siphoners:
            set_behaviour(
                self.connection,
                s.name,
                BHVR_EXTRACT_AND_TRANSFER,
                {"asteroid_wp": self.gas_giant, "cargo_to_transfer": ["*"]},
            )

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
        from public."refinery_FUEL" where system_symbol = %s"""
        results = try_execute_select(
            self.connection, sql, (self.starting_system.symbol,)
        )
        if not results:
            return None
        closest_distance = float("inf")
        closest_refinery = None
        relative_to = relative_to or Waypoint("", "", "", 0, 0, [], [], {}, {})

        for refinery in results:
            wp = Waypoint(*refinery, [], [], {}, {})
            d = self.pathfinder.calc_distance_between(relative_to, wp)
            if d < closest_distance:
                closest_distance = d
                closest_refinery = wp

        return closest_refinery

    def any_refuels_needed(self):
        waypoints = self.st.find_waypoints_by_trait(
            self.starting_system.symbol, "MARKETPLACE"
        )
        markets = [self.st.system_market(wp) for wp in waypoints]
        for market in markets:
            fuel = market.get_tradegood("FUEL")
            if fuel and fuel.type == "EXCHANGE" and fuel.supply != "ABUNDANT":
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
        self.haulers = [ship for ship in ships if ship.role == "HAULER"]
        self.commanders = [ship for ship in ships if ship.role == "COMMAND"]
        self.hounds = [ship for ship in ships if ship.frame.symbol == "FRAME_MINER"]
        self.extractors = [ship for ship in ships if ship.role == "EXCAVATOR"]
        self.refiners = [ship for ship in ships if ship.role == "REFINERY"]
        self.surveyors = [ship for ship in ships if ship.role == "SURVEYOR"]
        self.siphoners = [ship for ship in ships if ship.role == "SIPHONER"]

    def get_trade_routes(
        self, limit=None, min_market_depth=100, max_market_depth=1000000
    ) -> list[tuple]:
        if not limit:
            limit = len(self.haulers)
        sql = """select route_value, system_symbol, trade_symbol, profit_per_unit, export_market, import_market, market_depth
        from trade_routes_intrasystem tris
        where market_depth >= %s
        and market_depth <= %s
        limit %s"""
        routes = try_execute_select(
            self.connection, sql, (min_market_depth, max_market_depth, limit)
        )
        if not routes:
            return []

        return [(r[2], r[4], r[5], r[3]) for r in routes]


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


if __name__ == "__main__":
    set_logging()
    user = json.load(open("user.json"))
    logger.info("Starting up conductor, preparing to connect to database")
    logger.info("Connected to database")
    agents = []
    agents_and_clients: dict[str:SpaceTraders] = {}
    FuelManagementConductor(user).run()