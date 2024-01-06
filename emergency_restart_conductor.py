from datetime import datetime, timedelta
import logging
import json
from time import sleep
import math

import threading
from straders_sdk.models import Waypoint, Faction
from straders_sdk.ship import Ship
from straders_sdk.client_mediator import SpaceTradersMediatorClient as SpaceTraders
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

from conductor_functions import (
    set_behaviour,
    maybe_buy_ship_sys2,
    log_task,
    wait_until_reset,
    missing_market_prices,
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

        self.game_plan_path = user.get("custom_game_plan", "game_plan.json")
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
        self.siphoners = []
        self.refiners = []
        self.pathfinder = PathFinder(connection=self.connection)

        self.next_quarterly_update = None
        self.next_daily_update = None
        self.starting_system = None
        self.safety_margin = 0

        self.managed_systems: list[ConductorSystem] = []

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

        self.next_quarterly_update = datetime.now() + timedelta(minutes=1)
        self.next_hourly_update = datetime.now() + timedelta(hours=1)

        self.next_daily_update = datetime.now() + timedelta(days=1)
        #
        # hourly calculations of profitable things, assign behaviours and tasks
        #
        ships = self.all_ships = list(self.st.ships_view().values())
        ships.sort(key=lambda ship: ship.index)
        # rerun the hourly thing after we've calculated "ships we might buy"
        starting_run = True

        start_system = ConductorSystem()
        start_system.system_symbol = self.starting_system.symbol
        start_system.commander_trades = True
        start_system.probes_to_monitor_markets = True
        self.populate_ships(ships, start_system)
        while True:
            logging.info(
                f"Conductor is running - Q{self.next_quarterly_update.strftime('%H:%M:%S')}, H{self.next_hourly_update.strftime('%H:%M:%S')}, D{self.next_daily_update.strftime('%H:%M:%S')}"
            )
            self.st.view_my_self()
            ships = list(self.st.ships_view().values())
            ships.sort(key=lambda ship: ship.index)

            if self.next_hourly_update < datetime.now() or starting_run:
                self.hourly_update(start_system)
                self.next_hourly_update = datetime.now() + timedelta(hours=1)
            reset_quarterly = False
            reset_hourly = False
            reset_daily = False

            if reset_quarterly:
                self.next_quarterly_update = datetime.now() + timedelta(minutes=15)
            if reset_hourly:
                self.next_hourly_update = datetime.now() + timedelta(hours=1)
            if reset_daily:
                self.next_daily_update = datetime.now() + timedelta(days=1)
            starting_run = False
            # here for testing purposes only - remove this

            # minutely tasks, for scaling ships if possible.

            sleep(60)

    def system_daily_update(self, system: "ConductorSystem"):
        """Set ship behaviours and tasks"""

    def hourly_update(self, system: "ConductorSystem"):
        """Set ship behaviours and tasks"""

        for ship in self.all_ships:
            set_behaviour(self.connection, ship.name, "DISABLED FOR EMERGENCY", {})

        self.set_probe_tasks(system)
        for commander in system.commanders:
            set_behaviour(
                self.connection,
                commander.name,
                bhvr.BHVR_EMERGENCY_REBOOT,
                {"priority": 3},
            )
        possible_haulers = math.floor(self.st.view_my_self().credits / 1000000) + 1
        for i in range(possible_haulers):
            if system.haulers:
                hauler = system.haulers.pop(0)
                set_behaviour(self.connection, hauler.name, bhvr.BHVR_CHAIN_TRADE, {})

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

    def set_commander_tasks(self, system: "ConductorSystem") -> int:
        if system.commander_trades:
            commander = self.st.ships_view_one(f"{self.current_agent_symbol}-1")
            set_behaviour(
                self.connection,
                commander.name,
                BHVR_CHAIN_TRADE,
                {"priority": 3, "target_sys": system.system_symbol},
            )

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


class ConductorSystem:
    system_symbol: str
    # in order of priority
    commander_trades: bool = False

    hauler_tradegood_manage_jobs: list[str] = []
    haulers_chain_trading: int = 0
    haulers_doing_missions: int = 0
    probes_to_monitor_markets: bool = False
    probes_to_monitor_shipyards: bool = False
    use_explorers_as_haulers: bool = False
    construct_jump_gate: bool = False
    mining_sites: list[str] = []

    extractors_per_asteroid: int = 0
    extractors_per_engineered_asteroid: int = 0
    extractors_per_gas_giant: int = 0
    extractor_type_to_use: str = "SHIP_MINING_DRONE"
    surveyors_per_asteroid: int = 0

    siphoners_per_gas_giant: int = 0

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
    _siphoner_job_count = 0

    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)

    def to_json(self):
        out_dict = self.to_dict()
        return json.dumps(out_dict, indent=4)

    def to_dict(self):
        return {
            "system_symbol": self.system_symbol,
            "commander_trades": self.commander_trades,
            "hauler_tradegood_manage_jobs": self.hauler_tradegood_manage_jobs,
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
            "haulers_doing_missions": self.haulers_doing_missions,
            "construct_jump_gate": self.construct_jump_gate,
            "siphoners_per_gas_giant": self.siphoners_per_gas_giant,
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

    #    `tradegood`: the symbol of the tradegood to buy\n
    # optional:\n
    # `buy_wp`: if you want to specify a source market, provide the symbol.\n
    # `sell_wp`: if you want the ship to sell the cargo, set which waypoint\n

    # `max_buy_price`: if you want to limit the purchase price, set it here\n
    # `min_sell_price`: if you want to limit the sell price, set it here\n
    conductor = BehaviourConductor(user)

    conductor.run()
