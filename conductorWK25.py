from datetime import datetime, timedelta
import logging
import json
from time import sleep

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
import os
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
        password = os.environ.get("ST_DB_PASS", None)
        if not password:
            password = os.environ.get("ST_DB_PASSWORD", None)
        client = self.st = SpaceTraders(
            self.current_agent_token,
            db_host=os.environ.get("ST_DB_HOST", None),
            db_port=os.environ.get("ST_DB_PORT", None),
            db_name=os.environ.get("ST_DB_NAME", None),
            db_user=os.environ.get("ST_DB_USER", None),
            db_pass=password,
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
        self._refresh_game_plan(self.game_plan_path)
        # rerun the hourly thing after we've calculated "ships we might buy"
        starting_run = True

        while True:
            logging.info(
                f"Conductor is running - Q{self.next_quarterly_update.strftime('%H:%M:%S')}, H{self.next_hourly_update.strftime('%H:%M:%S')}, D{self.next_daily_update.strftime('%H:%M:%S')}"
            )
            self.st.view_my_self()
            ships = list(self.st.ships_view().values())
            ships.sort(key=lambda ship: ship.index)

            if self.next_daily_update < datetime.now() or starting_run:
                self.next_daily_update = datetime.now() + timedelta(days=1)
                # daily tasks like DB maintenance
                self.global_daily_update()

            if self.next_hourly_update < datetime.now() or starting_run:
                self.global_hourly_update()
            reset_quarterly = False
            reset_hourly = False
            reset_daily = False
            for system in self.managed_systems:
                self.populate_ships(ships, system)
                # daily reset uncharted waypoints.
                # hourly set ship behaviours
                # quarterly set ship tasks
                # minutely try and buy new ships

                if self.next_daily_update < datetime.now():
                    reset_daily = True
                    # daily tasks like DB maintenance
                    self.global_daily_update()

                if self.next_hourly_update < datetime.now():
                    reset_hourly = True
                    self.system_hourly_update(system)
                    # hourly tasks - for setting behaviours and such

                if self.next_quarterly_update < datetime.now():
                    reset_quarterly = True
                    self.system_quarterly_update(system)
                    # quartrly tasks - doesn't do anything presently

                if starting_run:
                    self.system_daily_update(system)
                    self.system_hourly_update(system)
                    self.system_quarterly_update(system)
                self.system_minutely_update(system)

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

    def global_daily_update(self):
        """Reset uncharted waypoints and refresh materialised views."""

        # step 1 - reset the uncharted waypoints. Mark them as "unchecked" and remove the uncharted trait.

        sql = """update waypoints  set checked = False where waypoint_symbol in (
            select waypoint_symbol from waypoint_traits wt where wt.trait_symbol = 'UNCHARTED' 
        );
        delete from waypoint_traits where trait_symbol = 'UNCHARTED';

        """
        result = try_execute_upsert(self.connection, sql, ())

        # step 2 - refresh the materialised views
        # this takes over 10 minutes, let's _not_ do it like this, and rethink. or at least do it on a seperate thread so it's not blocking.

        # step 3 - set default game plan
        self._generate_game_plan()
        self._refresh_game_plan()
        pass

    def system_daily_update(self, system: "ConductorSystem"):
        """Set ship behaviours and tasks"""

    def global_hourly_update(self):
        """Set ship behaviours and tasks"""
        self._refresh_game_plan(self.game_plan_path)

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

        if missing_market_prices(self.connection, system.system_symbol, 3):
            best_ship = system.commanders[0] if len(system.commanders) > 0 else None
            if not best_ship:
                best_ship = system.explorers[0] if len(system.explorers) > 0 else None
            if not best_ship:
                best_ship = system.haulers[0] if len(system.haulers) > 0 else None
            if not best_ship:
                best_ship = system.satellites[0] if len(system.satellites) > 0 else None
            if not best_ship:
                # the system is empty, so we should log this task to a globally available ship.
                return
            log_task(
                self.connection,
                bhvr.BHVR_EXPLORE_SYSTEM,
                [],
                system.system_symbol,
                5,
                self.current_agent_symbol,
                {"target_sys": system.system_symbol, "priority": 3},
                specific_ship_symbol=best_ship.name,
                expiry=self.next_hourly_update + timedelta(hours=1),
            )
        self.set_commander_tasks(system)
        system._probe_job_count = self.set_probe_tasks(system)
        system._hauler_job_count = self.set_hauler_tasks(system)
        system._extractor_job_count = self.set_extractor_tasks(system)
        system._siphoner_job_count = self.set_siphoner_tasks(system)

    def system_quarterly_update(self, system: "ConductorSystem"):
        # if the system's "buy_next_ship" attribute is set, log a task to buy it.

        if system._next_ship_to_buy:
            best_ship = None
            if len(system.explorers) > 0:
                best_ship = system.explorers[0]
            elif len(system.commanders) > 0:
                best_ship = system.commanders[0]
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
                    self.next_quarterly_update + timedelta(minutes=15),
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
            hauler_type = None
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
            if hauler_type:
                resp = maybe_buy_ship_sys2(
                    self.st,
                    system,
                    hauler_type,
                    len(system.haulers) * 50000 + 150000,
                )
                if resp:
                    self.haulers.append(resp)
                    self.set_hauler_tasks(system)
                else:
                    system._next_ship_to_buy = hauler_type

        if len(system.extractors) < system._extractor_job_count:
            resp = maybe_buy_ship_sys2(
                self.st,
                system,
                system.extractor_type_to_use,
                len(system.haulers) * 50000 + 150000,
            )
            if resp:
                self.extractors.append(resp)
                self.set_extractor_tasks(system)
            else:
                system._next_ship_to_buy = system.extractor_type_to_use
        if len(system.siphoners) < system._siphoner_job_count:
            resp = maybe_buy_ship_sys2(
                self.st,
                system,
                "SHIP_SIPHON_DRONE",
                len(system.haulers) * 50000 + 150000,
            )
            if resp:
                self.siphoners.append(resp)
                self.set_siphoner_tasks(system)
            else:
                system._next_ship_to_buy = "SHIP_SIPHON_DRONE"

        if len(system.satellites) < system._probe_job_count:
            if "SHIP_PROBE" in system.ship_type_shipyards:
                resp = maybe_buy_ship_sys2(
                    self.st,
                    system,
                    "SHIP_PROBE",
                    len(system.haulers) * 50000,
                )
                if resp:
                    self.satellites.append(resp)
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
            len(system.hauler_tradegood_manage_jobs)
            + system.haulers_chain_trading
            + system.haulers_doing_missions
            + 1
            if system.construct_jump_gate
            else 0
        )
        # set up the haulers to go to the markets and buy stuff
        if system.use_explorers_as_haulers:
            ships = system.explorers[:] + system.haulers[:]
        else:
            ships = system.haulers[:]
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

        for i in range(system.haulers_doing_missions):
            if len(ships) == 0:
                break
            hauler = ships.pop(0)
            set_behaviour(
                self.connection,
                hauler.name,
                bhvr.BHVR_EXECUTE_CONTRACTS,
                {"priority": 3},
            )
        if system.construct_jump_gate:
            if len(ships) == 0:
                return hauler_jobs
            hauler = ships.pop(0)
            set_behaviour(
                self.connection,
                hauler.name,
                bhvr.BHVR_CONSTRUCT_JUMP_GATE,
                {"priority": 4, "target_sys": system.system_symbol},
            )

        while len(ships) > 0:
            hauler = ships.pop(0)
            set_behaviour(
                self.connection,
                hauler.name,
                "EXCESS TO SYSTEM GAME PLAN",
                {"priority": 5},
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

    def set_siphoner_tasks(self, system: "ConductorSystem") -> int:
        siphoner_jobs = 0
        siphoners = system.siphoners[:]
        gas_giants = self.st.find_waypoints_by_type(system.system_symbol, "GAS_GIANT")
        for wayp in gas_giants:
            wayp
            siphoners_for_wayp = 0
            if wayp.type == "GAS_GIANT":
                siphoner_jobs += system.siphoners_per_gas_giant
                siphoners_for_wayp = system.siphoners_per_gas_giant
            for i in range(siphoners_for_wayp):
                if len(siphoners) == 0:
                    break
                siphoner = siphoners.pop(0)
                set_behaviour(
                    self.connection,
                    siphoner.name,
                    BHVR_EXTRACT_AND_GO_SELL,
                    {"asteroid_wp": wayp.symbol},
                )
        return siphoner_jobs

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
        pass
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

    def _generate_game_plan(self, filename="game_plan.json"):
        st = self.st
        #
        # STARTING SYSTEM
        #
        systems_being_managed = [s.system_symbol for s in self.managed_systems]
        start_system_s = waypoint_slicer(st.view_my_self().headquarters)
        start_system_obj = st.systems_view_one(waypoint_slicer(start_system_s))

        start_system = ConductorSystem(system_symbol=start_system_s)

        if start_system_s not in systems_being_managed:
            # we need to do some of this below anyway - but only want to add it if we're not already managing it.
            self.managed_systems.append(start_system)
        # trading & hauler stuff
        start_system.hauler_tradegood_manage_jobs = [
            "SHIP_PARTS",
            "SHIP_PLATING",
            "JEWELRY",
            "MEDICINE",
            "CLOTHING",
            "FOOD",
            "FUEL",
            "FUEL",
        ]
        start_system.haulers_chain_trading = 2
        start_system.probes_to_monitor_shipyards = True
        start_system.probes_to_monitor_markets = True
        start_system.haulers_doing_missions = 1
        gate_complete = True
        start_gate = st.find_waypoints_by_type(start_system_s, "JUMP_GATE")
        if start_gate:
            gate = start_gate[0]
            gate: Waypoint
            gate_complete = gate.under_construction
            if gate.under_construction:
                start_system.construct_jump_gate = True
                start_system.commander_trades = True
            else:
                start_system.commander_trades = False
                # reset this so the commander can be used to seed the system.
                for l_system in self.managed_systems:
                    l_system.commander_trades = False
        # extractors and siphoners
        start_system.siphoners_per_gas_giant = 5

        start_system.extractors_per_engineered_asteroid = 20
        e = st.find_waypoints_by_type(start_system_s, "ENGINEERED_ASTEROID")
        if e:
            start_system.mining_sites = [w.symbol for w in e]

        if gate_complete:
            start_system.construct_jump_gate = False
            # we need populate the next HQ system - starting with our own.
            factions = st.list_factions()
            # sort them by distance to our location
            factions = [f for f in factions if f.is_recruiting]
            faction = factions[len(self.managed_systems) - 2]

            faction: Faction
            faction.headquarters
            faction_hq_syss = [
                st.systems_view_one(waypoint_slicer(s.headquarters)) for s in factions
            ]
            faction_hq_syss.sort(
                key=lambda s: self.pathfinder.calc_distance_between(start_system_obj, s)
            )
            # there's at least one managed system, so we can pick the next one based on the length of the managed systems property
            next_system = faction_hq_syss[len(self.managed_systems) - 2]
            next_system = ConductorSystem(system_symbol=next_system.symbol)
            self.managed_systems.append(next_system)

            next_system.commander_trades = True
            next_system.hauler_tradegood_manage_jobs = ["ANTIMATTER"]
            for i in range(1):
                symbols = [
                    "SHIP_PARTS",
                    "SHIP_PLATING",
                    "JEWELRY",
                    "MEDICINE",
                    "CLOTHING",
                    "FOOD",
                    "FUEL",
                    "FUEL",
                ]
                for s in symbols:
                    next_system.hauler_tradegood_manage_jobs.append(s)
            next_system.haulers_chain_trading = 4
            next_system.probes_to_monitor_markets = True
            next_system.probes_to_monitor_shipyards = True
            next_system.use_explorers_as_haulers = True
            next_system.siphoners_per_gas_giant = 0
            next_system.commander_trades = True
        else:
            start_system.construct_jump_gate = True

        self._save_game_plan("game_plan.json")

    def _save_game_plan(self, filename="game_plan.json"):
        with open(filename, "w") as f:
            jso = {"systems": [s.to_dict() for s in self.managed_systems]}
            json.dump(jso, f, indent=4)

    def _refresh_game_plan(self, filename="game_plan.json"):
        "load the game_plan.json file"
        # this is overriding everything and loading it again needlessly.
        # it's not even using local caches for the market and shipyard - you'll want to change this to update managed_systems with new values instead.

        try:
            with open(filename) as f:
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
