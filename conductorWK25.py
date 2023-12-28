from datetime import datetime, timedelta
import logging, math
import json
from time import sleep
from functools import partial

import psycopg2.sql
from itertools import zip_longest


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
    BHVR_MONITOR_SPECIFIC_LOCATION,
    BHVR_MANAGE_SPECIFIC_EXPORT,
    BHVR_SELL_OR_JETTISON_ALL_CARGO,
    BHVR_CHAIN_TRADE,
)
import behaviour_constants as bhvr

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
    maybe_buy_ship_sys2,
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

    def __init__(
        self, user: dict[str, str], connection=None, session=None, target_agent=None
    ) -> None:
        if target_agent:
            for tup in user.get("agents"):
                if tup["username"] == target_agent:
                    self.current_agent_symbol = tup["username"]
                    self.current_agent_token = tup["token"]
        else:
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
        self.connection = client.connection
        self.haulers = []
        self.commanders = []
        self.hounds = []
        self.explorers = []
        self.extractors = []
        self.surveyors = []
        self.satellites = []
        self.refiners = []
        self.pathfinder = PathFinder(connection=self.connection)

        self.next_quarterly_update = None
        self.next_daily_update = None
        self.starting_system = None
        self.safety_margin = 0

        self.managed_systems = list[ConductorSystem]

        # * progress missions
        hq = self.st.view_my_self().headquarters
        hq_sys = waypoint_slicer(hq)

        # initial integrity check
        ships = self.st.ships_view()
        if not ships:
            ships = self.st.ships_view(True)
        self.starting_system = self.st.systems_view_one(hq_sys)
        if not self.starting_system:
            self.starting_system = self.st.systems_view_one(hq_sys)

        self.starting_planet = self.st.waypoints_view_one(hq)

        for sym in self.starting_system.waypoints:
            wp = self.st.waypoints_view_one(sym.symbol)
            if "MARKETPLACE" in [t.symbol for t in wp.traits]:
                self.st.system_market(wp)
            if "SHIPYARD" in [t.symbol for t in wp.traits]:
                self.st.system_shipyard(wp)
            if wp.type == "JUMP_GATE":
                self.st.system_jumpgate(wp)
                self.jump_gate = wp

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
        ships = self.all_ships = list(self.st.ships_view().values())
        ships.sort(key=lambda ship: ship.index)
        # rerun the hourly thing after we've calculated "ships we might buy"
        starting_run = True
        while True:
            logging.info("Conductor is running")
            self.st.view_my_self()
            ships = list(self.st.ships_view().values())
            ships.sort(key=lambda ship: ship.index)

            if self.next_daily_update < datetime.now() or starting_run:
                self.next_daily_update = datetime.now() + timedelta(days=1)
                # daily tasks like DB maintenance
                self.daily_update()

            if self.next_hourly_update < datetime.now() or starting_run:
                self.global_hourly_update()

            for system in self.managed_systems:
                self.populate_ships(ships, system)
                # daily reset uncharted waypoints.
                # hourly set ship behaviours
                # quarterly set ship tasks
                # minutely try and buy new ships

                if self.next_daily_update < datetime.now():
                    self.next_daily_update = datetime.now() + timedelta(days=1)
                    # daily tasks like DB maintenance
                    self.daily_update()

                if self.next_hourly_update < datetime.now():
                    self.next_hourly_update = datetime.now() + timedelta(hours=1)
                    self.system_hourly_update(system)
                    # hourly tasks - for setting behaviours and such

                if self.next_quarterly_update < datetime.now():
                    self.next_quarterly_update = datetime.now() + timedelta(minutes=15)
                    self.system_quarterly_update(system)
                    # quartrly tasks - doesn't do anything presently

                if starting_run:
                    self.system_daily_update(system)
                    self.system_hourly_update(system)
                    self.system_quarterly_update(system)

                self.system_minutely_update(system)
            starting_run = False
            # here for testing purposes only - remove this

            # minutely tasks, for scaling ships if possible.

            sleep(60)

    def daily_update(self):
        """Reset uncharted waypoints and refresh materialised views."""
        pass

    def system_daily_update(self, system: "ConductorSystem"):
        """Set ship behaviours and tasks"""

    def global_hourly_update(self):
        """Set ship behaviours and tasks"""
        self._refresh_game_plan()

        pass

    def system_hourly_update(self, system: "ConductorSystem"):
        """Set ship behaviours and tasks"""
        # jettison for all haulers in th system - explorers too if setting is on.
        for ship in system.haulers + (
            system.explorers if system.use_explorers_as_haulers else []
        ):
            if ship.cargo_units_used > 0:
                log_task(
                    self.connection,
                    BHVR_SELL_OR_JETTISON_ALL_CARGO,
                    [],
                    system.system_symbol,
                    5,
                    self.current_agent_symbol,
                    specific_ship_symbol=ship.name,
                )
        system._probe_job_count = self.set_probe_tasks(system)
        system._hauler_job_count = self.set_hauler_tasks(system)
        system._extractor_job_count = self.set_extractor_tasks(system)

    def system_quarterly_update(self, system: "ConductorSystem"):
        # if the system's "buy_next_ship" attribute is set, log a task to buy it.

        if system._next_ship_to_buy:
            best_ship = None
            if len(system.explorers) > 0:
                best_ship = system.explorers[0]
            elif len(system.haulers) > 0:
                best_ship = system.haulers[0]
            elif len(system.satellites) > 0:
                best_ship = system.satellites[0]
            if best_ship:
                log_task(
                    self.connection,
                    bhvr.BHVR_GO_AND_BUY_A_SHIP,
                    [],
                    system.system_symbol,
                    1,
                    self.current_agent_symbol,
                    {"ship_type": system._next_ship_to_buy},
                    self.next_quarterly_update,
                    best_ship.name,
                )
                system._next_ship_to_buy = None

        pass

    def global_quarterly_update(self):
        pass

    def system_minutely_update(self, system: "ConductorSystem"):
        """Buy ships if possible"""
        system._next_ship_to_buy = None

        haulers = (
            system.haulers + system.explorers
            if system.use_explorers_as_haulers
            else system.haulers
        )

        if len(haulers) < system._hauler_job_count:
            if "SHIP_HEAVY_FREIGHTER" in system.ship_type_shipyards:
                hauler_type = "SHIP_HEAVY_FREIGHTER"
            elif (
                system.use_explorers_as_haulers
                and "SHIP_EXPLORER" in system.ship_type_shipyards
            ):
                hauler_type = "SHIP_EXPLORER"
            elif "SHIP_LIGHT_HAULER" in system.ship_type_shipyards:
                hauler_type = "SHIP_LIGHT_HAULER"
            elif "SHIP_LIGHT_SHUTTLE" in system.ship_type_shipyards:
                hauler_type = "SHIP_LIGHT_SHUTTLE"
            resp = maybe_buy_ship_sys2(
                self.st,
                system,
                hauler_type,
                len(system.haulers) * 50000,
            )
            if resp:
                self.set_hauler_tasks(system)
            else:
                system._next_ship_to_buy = hauler_type

        if len(system.extractors) < system._extractor_job_count:
            resp = maybe_buy_ship_sys2(
                self.st,
                system,
                system.extractor_type_to_use,
                len(system.haulers) * 50000,
            )
            if resp:
                self.set_extractor_tasks(system)
            else:
                system._next_ship_to_buy = system.extractor_type_to_use
        if len(system.satellites) < system._probe_job_count:
            if "SHIP_PROBE" in system.ship_type_shipyards:
                resp = maybe_buy_ship_sys2(
                    self.st,
                    system,
                    "SHIP_PROBE",
                    len(system.haulers) * 50000,
                )
                if resp:
                    self.set_probe_tasks(system)
                else:
                    system._next_ship_to_buy = "SHIP_PROBE"

    def set_probe_tasks(self, system: "ConductorSystem") -> int:
        satellites = system.satellites[:]
        probe_jobs = 0
        if system.probes_to_monitor_shipyards:
            # find each distinct coordinate
            shipyards = list(set([w for w in system.ship_type_shipyards.values()]))
            if "SHIP_PROBE" in system.ship_type_shipyards:
                target_waypoint = system.ship_type_shipyards["SHIP_PROBE"]
                shipyards.remove(target_waypoint)
                if len(system.satellites) == 0:
                    return len(shipyards) + 1
                probe = satellites.pop(0)
                set_behaviour(
                    self.connection,
                    probe.name,
                    BHVR_MONITOR_SPECIFIC_LOCATION,
                    {"waypoint": target_waypoint},
                )
            for shipyard in shipyards:
                if len(satellites) == 0:
                    break
                probe = satellites.pop(0)
                set_behaviour(
                    self.connection,
                    probe.name,
                    BHVR_MONITOR_SPECIFIC_LOCATION,
                    {"waypoint": shipyard},
                )
            probe_jobs += len(shipyards) + 1

        if system.probes_to_monitor_markets:
            # find each distinct coordinate
            market_symbols = [w for w in system.tradegoods_exported.values()]
            market_symbols.extend([w for w in system.tradegoods_imported.values()])
            market_symbols = [item for list in market_symbols for item in list]
            market_symbols = set(market_symbols)
            coords = {}
            for symbol in market_symbols:
                wp = self.st.waypoints_view_one(symbol)
                coords[f"{wp.x},{wp.y}"] = symbol
            satellites = system.satellites
            for symbol in market_symbols:
                if len(satellites) == 0:
                    break
                probe = satellites.pop(0)
                set_behaviour(
                    self.connection,
                    probe.name,
                    BHVR_MONITOR_SPECIFIC_LOCATION,
                    {"waypoint": symbol, "priority": 5},
                )
            probe_jobs += len(coords)
        return probe_jobs

    def set_hauler_tasks(self, system: "ConductorSystem") -> int:
        hauler_jobs = (
            len(system.hauler_tradegood_manage_jobs) + system.haulers_chain_trading
        )
        # set up the haulers to go to the markets and buy stuff
        if system.use_explorers_as_haulers:
            ships = system.explorers[:] + system.haulers[:]
        else:
            ships = system.haulers
        for tradegood in system.hauler_tradegood_manage_jobs:
            if len(ships) == 0:
                break
            if tradegood not in system.tradegoods_exported:
                continue

            for target_wayp in system.tradegoods_exported[tradegood]:
                if len(ships) == 0:
                    break
                hauler = ships.pop(0)
                set_behaviour(
                    self.connection,
                    hauler.name,
                    # for now manage single, eventually manage supply chain
                    BHVR_MANAGE_SPECIFIC_EXPORT,
                    {
                        "target_tradegood": tradegood,
                        "market_wp": target_wayp,
                        "priority": 4,
                    },
                    # {} "tradegood": tradegood, "buy_wp": import_wp, "sell_wp": export_wp},
                )
        for i in range(system.haulers_chain_trading):
            if len(ships) == 0:
                break
            hauler = ships.pop(0)
            set_behaviour(
                self.connection,
                hauler.name,
                # for now manage single, eventually manage supply chain
                BHVR_CHAIN_TRADE,
                {"priority": 3},
                # {} "tradegood": tradegood, "buy_wp": import_wp, "sell_wp": export_wp},
            )
        return hauler_jobs

    def set_extractor_tasks(self, system: "ConductorSystem") -> int:
        extractor_jobs = 0
        extractors = system.extractors[:]
        for wayp_s in system.mining_sites:
            wayp = self.st.waypoints_view_one(wayp_s)
            extractors_for_wayp = 0
            if wayp.type == "ASTEROID":
                extractor_jobs += system.extractors_per_asteroid
                extractors_for_wayp = system.extractors_per_asteroid
            elif wayp.type == "ENGINEERED_ASTEROID":
                extractor_jobs += system.extractors_per_engineered_asteroid
                extractors_for_wayp = system.extractors_per_engineered_asteroid
            for i in range(extractors_for_wayp):
                if len(extractors) == 0:
                    break
                extractor = extractors.pop(0)
                set_behaviour(
                    self.connection,
                    extractor.name,
                    BHVR_EXTRACT_AND_GO_SELL,
                    {"asteroid_wp": wayp_s},
                )
        return extractor_jobs

    def populate_ships(self, ships: list[Ship], system: "ConductorSystem"):
        "Set the conductor's ship lists, and subdivides them into roles."
        ships = [
            ship for ship in ships if ship.nav.system_symbol == system.system_symbol
        ]
        system.satellites = [ship for ship in ships if ship.role == "SATELLITE"]
        system.haulers = [ship for ship in ships if ship.role in ("HAULER")]
        system.shuttles = [ship for ship in ships if ship.role == "TRANSPORT"]
        system.commanders = [ship for ship in ships if ship.role == "COMMAND"]
        system.hounds = [ship for ship in ships if ship.frame.symbol == "FRAME_MINER"]
        system.extractors = [
            ship for ship in ships if ship.role == "EXCAVATOR" and ship.can_extract
        ]
        system.explorers = [ship for ship in ships if ship.role == "EXPLORER"]
        system.refiners = [ship for ship in ships if ship.role == "REFINERY"]
        system.surveyors = [ship for ship in ships if ship.role == "SURVEYOR"]
        system.siphoners = [
            ship for ship in ships if ship.role == "EXCAVATOR" and ship.can_siphon
        ]

    def _refresh_game_plan(self):
        "load the game_plan.json file"
        # this is overriding everything and loading it again needlessly.
        # it's not even using local caches for the market and shipyard - you'll want to change this to update managed_systems with new values instead.

        try:
            with open("game_plan.json") as f:
                jso = json.load(f)
                self.managed_systems = [
                    ConductorSystem.from_dict(d) for d in jso["systems"]
                ]
        except (FileNotFoundError, json.JSONDecodeError) as err:
            logger.error(f"Error loading game_plan.json: {err}")
            self.managed_systems = []

        for system in self.managed_systems:
            system.ship_type_shipyards = {}
            system.tradegoods_exported = {}
            system.tradegoods_imported = {}
            wayps = self.st.waypoints_view(system.system_symbol)
            for wayp in wayps.values():
                wayp: Waypoint
                if "SHIPYARD" in [trait.symbol for trait in wayp.traits]:
                    sy = self.st.system_shipyard(wayp)
                    for sy in sy.ship_types:
                        system.ship_type_shipyards[sy] = wayp.symbol
                if "MARKETPLACE" in [trait.symbol for trait in wayp.traits]:
                    market = self.st.system_market(wayp)
                    for good in market.exports:
                        if good.symbol not in system.tradegoods_exported:
                            system.tradegoods_exported[good.symbol] = []
                        system.tradegoods_exported[good.symbol].append(wayp.symbol)
                    for good in market.imports:
                        if good.symbol not in system.tradegoods_imported:
                            system.tradegoods_imported[good.symbol] = []
                        system.tradegoods_imported[good.symbol].append(wayp.symbol)
                    for good in market.listings:
                        if (
                            good.type == "EXPORT"
                            and good.symbol not in system.tradegoods_exported
                        ):
                            system.tradegoods_exported[good.symbol] = []
                            if (
                                wayp.symbol
                                not in system.tradegoods_exported[good.symbol]
                            ):
                                system.tradegoods_exported[good.symbol].append(
                                    wayp.symbol
                                )
                        if (
                            good.type == "IMPORT"
                            and good.symbol not in system.tradegoods_imported
                        ):
                            system.tradegoods_imported[good.symbol] = []
                            if (
                                wayp.symbol
                                not in system.tradegoods_imported[good.symbol]
                            ):
                                system.tradegoods_imported[good.symbol].append(
                                    wayp.symbol
                                )


class ConductorSystem:
    system_symbol: str
    # in order of priority

    hauler_tradegood_manage_jobs: list[str] = []
    haulers_chain_trading: int = 0
    probes_to_monitor_markets: bool = False
    probes_to_monitor_shipyards: bool = False
    use_explorers_as_haulers: bool = False

    mining_sites: list[str] = []

    extractors_per_asteroid: int = 0
    extractors_per_engineered_asteroid: int = 0
    extractors_per_gas_giant: int = 0
    extractor_type_to_use: str = "SHIP_MINING_DRONE"
    surveyors_per_asteroid: int = 0

    commanders: list[Ship] = []
    satellites: list[Ship] = []
    haulers: list[Ship] = []
    shuttles: list[Ship] = []
    extractors: list[Ship] = []
    explorers: list[Ship] = []
    refiners: list[Ship] = []
    surveyors: list[Ship] = []
    siphoners: list[Ship] = []
    hounds: list[Ship] = []

    _next_ship_to_buy: str = None

    tradegoods_exported: dict[str : list[str]] = {}
    tradegoods_imported: dict[str : list[str]] = {}

    ship_type_shipyards: dict[str : list[Waypoint]] = {}
    target_mining_sites: list[str] = []
    # these values are calculated by the "set behaviour" method hourly, and used to define the limits of the ships we go for.
    _probe_job_count = 0
    _hauler_job_count = 0  # haulers are also explorers if the setting is on
    _extractor_job_count = 0

    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)

    def to_json(self):
        out_dict = self.to_dict()
        return json.dumps(out_dict, indent=4)

    def to_dict(self):
        return {
            "system_symbol": self.system_symbol,
            "tradegood_manage_jobs": self.hauler_tradegood_manage_jobs,
            "probes_to_monitor_markets": self.probes_to_monitor_markets,
            "probes_to_monitor_shipyards": self.probes_to_monitor_shipyards,
            "use_explorers_as_haulers": self.use_explorers_as_haulers,
            "mining_sites": self.mining_sites,
            "extractors_per_asteroid": self.extractors_per_asteroid,
            "extractors_per_engineered_asteroid": self.extractors_per_engineered_asteroid,
            "extractors_per_gas_giant": self.extractors_per_gas_giant,
            "extractor_type_to_use": self.extractor_type_to_use,
            "surveyors_per_asteroid": self.surveyors_per_asteroid,
            "haulers_chain_trading": self.haulers_chain_trading,
        }

    @classmethod
    def from_json(cls, json_string):
        return cls(**json.loads(json_string))

    @classmethod
    def from_dict(cls, dict):
        return cls(**dict)


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

    system = ConductorSystem()
    system.system_symbol = "PK-16"
    system.hauler_tradegood_manage_jobs = [
        "SHIP_PARTS",
        "SHIP_PLATING",
        "ADVANCED_CIRCUITRY",
        "ELECTRONICS",
        "MICROPROCESSORS",
        "EXPLOSIVES",
        "COPPER",
        "FUEL",
    ]
    system.probes_to_monitor_markets = True
    system.probes_to_monitor_shipyards = True
    system.use_explorers_as_haulers = True
    system.mining_sites = ["X1-PK16-AE5E", "X1-PK16-B40", "X1-PK16-B44"]
    system.extractors_per_asteroid = 10
    system.extractors_per_engineered_asteroid = 10
    system.extractor_type_to_use = "SHIP_MINING_DRONE"
    system.extractors_per_gas_giant = 10
    system.surveyors_per_asteroid = 2

    conductor.run()
