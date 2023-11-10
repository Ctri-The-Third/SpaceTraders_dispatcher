from datetime import datetime, timedelta
import logging
import json
from time import sleep
from functools import partial

import psycopg2.sql


from straders_sdk.local_response import LocalSpaceTradersRespose
from straders_sdk.models import Shipyard, ShipyardShip, Waypoint, Agent
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
)
from behaviours.generic_behaviour import Behaviour as GenericBehaviour

from conductor_functions import (
    process_contracts,
    get_prices_for,
    set_behaviour,
    maybe_buy_ship_sys,
    log_task,
)


logger = logging.getLogger(__name__)


class Conductor:

    """This class will manage the recon agents and their behaviour."""

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
        self.starting_planet = None
        self.capital_reserve = 0

    def run(self):
        #
        # * scale regularly and set defaults
        # * progress missions
        hq = self.st.view_my_self().headquarters
        hq_sys = waypoint_slicer(hq)
        self.starting_system = self.st.systems_view_one(hq_sys)
        self.starting_planet = self.st.waypoints_view_one(hq_sys, hq)

        self.next_quarterly_update = datetime.now() + timedelta(hours=1)
        last_quarterly_update = datetime.now() - timedelta(hours=2)
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

            if last_daily_update < datetime.now() - timedelta(days=1):
                self.daily_update()
                last_daily_update = datetime.now()
                self.next_daily_update = datetime.now() + timedelta(days=1)

            if last_quarterly_update < datetime.now() - timedelta(minutes=15):
                self.quarterly_update()
                last_quarterly_update = datetime.now()
                self.next_quarterly_update = datetime.now() + timedelta(minutes=15)

            self.minutely_update()
            if starting_run:
                self.daily_update()
                self.quarterly_update()
                starting_run = False
            sleep(60)

    def quarterly_update(self):
        st = self.st

        self.capital_reserve = 0
        hq = st.view_my_self().headquarters

        hq_sys = waypoint_slicer(hq)

        if not self.asteroid_wps:
            resp = st.find_waypoints_by_trait(
                self.starting_system.symbol, "COMMON_METAL_DEPOSITS"
            )
            if resp:
                partial_calc_dist = partial(
                    self.pathfinder.calc_distance_between, self.starting_planet
                )
                resp = sorted(resp, key=partial_calc_dist)
                self.asteroid_wps = resp

        for ship in self.extractors:
            set_behaviour(
                self.connection,
                ship.name,
                BHVR_EXTRACT_AND_TRANSFER,
                {"asteroid_wp": self.asteroid_wps[0].symbol},
            )
        for surveyor in self.surveyors:
            set_behaviour(
                self.connection,
                surveyor.name,
                BHVR_CHILL_AND_SURVEY,
                {"asteroid_wp": self.asteroid_wps[0].symbol},
            )
        for commander in self.commanders:
            set_behaviour(
                self.connection,
                commander.name,
                BHVR_EXTRACT_AND_GO_SELL,
                {"asteroid_wp": self.asteroid_wps[0].symbol},
            )
        # self.assign_traderoutes_to_ships(self.haulers)
        self.log_shallow_trade_tasks()

        # find unvisited shipyards

        #
        # visit unvisited shipyards
        #
        for ship in self.ships_we_might_buy:
            # get all possibilities
            sql = """select msstvf.system_symbol from mkt_shpyrds_systems_to_visit_first msstvf 
                    join systems s on msstvf.system_symbol = s.system_symbol
                    join waypoints w on w.system_symbol = s.system_symbol
                    join shipyard_types st on st.shipyard_symbol = w.waypoint_symbol
                    join systems_with_jumpgates swj on swj.system_symbol = s.system_symbol
                    where ship_type = %s
                    order by ship_cost = null, last_updated asc
                     

                    """

            rows = try_execute_select(self.connection, sql, (ship,))
            for row in rows:
                dest_system_wp = row[0]
                syst = st.systems_view_one(dest_system_wp)
                route = self.pathfinder.astar(self.starting_system, syst)

                if route and route.jumps > 0:
                    log_task(
                        self.connection,
                        BHVR_EXPLORE_SYSTEM,
                        ["DRONE"],
                        dest_system_wp,
                        priority=5,
                        behaviour_params={"target_sys": dest_system_wp},
                        expiry=self.next_quarterly_update,
                    )

                    # if we've found one that can be visited by drone, stop logging tasks.

                    break

        # find unvisited network gates
        refinables = ["IRON_ORE", "ALUMINUM_ORE", "COPPER_ORE"]
        extractables = [
            "IRON_ORE",
            "QUARTZ_SAND",
            "ICE_WATER",
            "ALUMINUM_ORE",
            "SILICON_CRYSTALS",
            "AMMONIA_ICE",
            "PRECIOUS_STONES",
            "COPPER_ORE",
        ]
        best_extractable = ("IRON_ORE", 0)
        best_refinable = ("IRON_ORE", 0)
        for refinable in refinables + extractables:
            prices = get_prices_for(self.connection, refinable, st.current_agent_symbol)
            if not prices:
                break
            if refinable in refinables:
                if prices[0] > best_refinable[1]:
                    best_refinable = (refinable, prices[0])
            if refinable in extractables:
                if prices[0] > best_extractable[1]:
                    best_extractable = (refinable, prices[0])

        # send refiners to asteroid
        for refiner in self.refiners:
            params = {"asteroid_wp": self.asteroid_wps[0].symbol}
            set_behaviour(
                self.connection, refiner.name, BHVR_RECEIVE_AND_REFINE, params
            )

        # send haulers to go buy things

    def daily_update(self):
        sql = """
            update waypoints w set checked = false where waypoint_symbol in (
                select waypoint_symbol from waypoint_traits wt where wt.trait_symbol = 'UNCHARTED'
            );
            delete from waypoint_traits WT where wt.trait_symbol = 'UNCHARTED';"""
        try_execute_upsert(self.connection, sql, [])
        self.pathfinder.clear_jump_graph()

        log_task(
            self.connection,
            BHVR_EXPLORE_SYSTEM,
            [],
            self.starting_system.symbol,
            1,
            self.st.current_agent_symbol,
            {"target_sys": self.starting_system.symbol},
            expiry=self.next_daily_update,
            specific_ship_symbol=self.satellites[0].name,
        )

    def minutely_update(self):
        """This method handles ship scaling and assigning default behaviours."""

        st = self.st

        st.current_agent = st.view_my_self()

        process_contracts(self.st)
        hounds = self.hounds
        refiners = self.refiners
        haulers = self.haulers
        #
        # this can be its own "scale up" method
        #
        behaviour_params = {"asteroid_wp": self.asteroid_wps[0].symbol}
        # stage 0 - pre warpgate.

        if (
            len(self.extractors) < 10
            or len(self.surveyors) < 1
            or len(self.haulers) < 1
        ):
            new_ship = None
            if len(self.haulers) < 1:
                new_ship = maybe_buy_ship_sys(st, "SHIP_LIGHT_HAULER")
                new_behaviour = BHVR_RECEIVE_AND_FULFILL
            if len(self.extractors) < 10 and not new_ship:
                new_ship = None  # maybe_buy_ship_sys(st, "SHIP_MINING_DRONE")
                new_behaviour = (
                    BHVR_EXTRACT_AND_GO_SELL
                    if len(self.haulers) == 0
                    else BHVR_EXTRACT_AND_TRANSFER
                )
            if len(self.surveyors) < 1 and not new_ship:
                new_ship = None  # maybe_buy_ship_sys(st, "SHIP_SURVEYOR")
                new_behaviour = BHVR_CHILL_AND_SURVEY

            self.ships_we_might_buy = [
                "SHIP_MINING_DRONE",
                "SHIP_SURVEYOR",
                "SHIP_LIGHT_HAULER",
            ]

        # stage 4
        elif len(hounds) <= 50 or len(refiners) < 1 or len(haulers) < 10:
            self.ships_we_might_buy = [
                "SHIP_PROBE",
                "SHIP_ORE_HOUND",
                "SHIP_HEAVY_FREIGHTER",
                "SHIP_COMMAND_FRIGATE",
                "SHIP_REFINING_FREIGHTER",
            ]
            new_ship = None
            if len(hounds) < 50:
                new_ship = maybe_buy_ship_sys(st, "SHIP_ORE_HOUND")
                new_behaviour = BHVR_EXTRACT_AND_GO_SELL
            if len(refiners) < 1 and not new_ship:
                new_ship = maybe_buy_ship_sys(st, "SHIP_REFINING_FREIGHTER")
                new_behaviour = BHVR_RECEIVE_AND_REFINE
            if len(haulers) < 10 and not new_ship:
                new_ship = maybe_buy_ship_sys(st, "SHIP_HEAVY_FREIGHTER")
                new_behaviour = BHVR_RECEIVE_AND_FULFILL
            pass
        else:
            new_ship = False

        if new_ship:
            set_behaviour(
                self.connection,
                new_ship.name,
                new_behaviour,
                behaviour_params=behaviour_params,
            )
            self.populate_ships()
        for i in list(range(len(self.ships_we_might_buy))):
            if len(self.satellites) <= i:
                ship = maybe_buy_ship_sys(st, "SHIP_PROBE")
            else:
                ship = self.satellites[i]

            if not ship:
                break
            set_behaviour(
                self.connection,
                ship.name,
                BHVR_MONITOR_CHEAPEST_PRICE,
                behaviour_params={"ship_type": self.ships_we_might_buy[i]},
            )
        self.maybe_upgrade_ship()

    def assign_traderoutes_to_ships(self, ships: list[Ship]):
        routes = self.get_trade_routes(len(ships))
        if not routes:
            return
        for i, ship in enumerate(ships):
            tradegood, buy_wp, sell_wp, profit_per_unit = routes[i]
            set_behaviour(
                self.connection,
                ship.name,
                BHVR_BUY_AND_DELIVER_OR_SELL,
                behaviour_params={
                    "buy_wp": buy_wp,
                    "sell_wp": sell_wp,
                    "tradegood": tradegood,
                    "safety_profit_threshold": profit_per_unit / 2,
                },
            )

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

    def get_trade_routes(self, limit=None, min_market_depth=100) -> list[tuple]:
        if not limit:
            limit = len(self.haulers)
        sql = """select route_value, system_symbol, trade_symbol, profit_per_unit, export_market, import_market, market_depth
        from trade_routes_intrasystem tris
        where market_depth >= %s
        limit %s"""
        routes = try_execute_select(self.connection, sql, (min_market_depth, limit))
        if not routes:
            return []

        return [(r[2], r[4], r[5], r[3]) for r in routes]

    def log_shallow_trade_tasks(self) -> int:
        working_capital = self.st.view_my_self().credits
        routes = self.get_shallow_trades(working_capital, limit=1)

        for route in routes:
            (
                trade_symbol,
                export_market,
                import_market,
                profit_per_unit,
                cost_to_execute,
            ) = route
            self.capital_reserve += cost_to_execute
            log_task(
                self.connection,
                BHVR_BUY_AND_DELIVER_OR_SELL,
                ["35_CARGO"],
                waypoint_slicer(import_market),
                5,
                self.current_agent_symbol,
                {
                    "buy_wp": export_market,
                    "sell_wp": import_market,
                    "quantity": 35,
                    "tradegood": trade_symbol,
                    "safety_profit_threshold": profit_per_unit / 2,
                },
                expiry=self.next_quarterly_update,
            )
        return self.capital_reserve

    def get_shallow_trades(
        self,
        working_capital: int,
        limit=50,
    ) -> list[tuple]:
        sql = """select trade_symbol, system_symbol, profit_per_unit, export_market, import_market, market_depth, purchase_price * 35
        from trade_routes_intrasystem tris
        where market_depth = 10 and purchase_price * 35 < %s
        limit %s"""

        routes = try_execute_select(
            self.connection,
            sql,
            (
                working_capital,
                limit,
            ),
        )
        if not routes:
            return []
        return [(r[0], r[3], r[4], r[2], r[6]) for r in routes]


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
    Conductor(user).run()
