# this is the ship dispatcher / conductor script.
# It will get unlocked ships from the DB, check their behaviour ID and if it matches a known behaviour, lock the ship and execute the behaviour.
import json
import logging
import signal
import math
import random
import psycopg2
import re
import sys, threading, os, uuid, time
from requests_ratelimiter import LimiterSession
from requests.adapters import HTTPAdapter
from straders_sdk.models import Agent
from straders_sdk import SpaceTraders
from straders_sdk.request_consumer import RequestConsumer
from straders_sdk.models import Waypoint
from straders_sdk.utils import set_logging, waypoint_slicer
from behaviours.extract_and_chill import (
    ExtractAndChill,
    BEHAVIOUR_NAME as BHVR_EXTRACT_AND_CHILL,
)
from behaviours.buy_and_sell_dripfeed import (
    BuyAndSellDripfeed,
    BEHAVIOUR_NAME as BHVR_BUY_AND_SELL_DRIPFEED,
)
from behaviours.extract_and_sell import (
    ExtractAndGoSell,
    BEHAVIOUR_NAME as BHVR_EXTRACT_AND_GO_SELL,
)
from behaviours.receive_and_fulfill import (
    ReceiveAndFulfillOrSell_3,
    BEHAVIOUR_NAME as BHVR_RECEIVE_AND_FULFILL,
)
from behaviours.generic_behaviour import Behaviour
from behaviours.extract_and_transfer import (
    ExtractAndTransfer_8,
    BEHAVIOUR_NAME as BHVR_EXTRACT_AND_TRANSFER,
)
from behaviours.remote_scan_and_survey import (
    RemoteScanWaypoints,
    BEHAVIOUR_NAME as BHVR_REMOTE_SCAN_AND_SURV,
)
from behaviours.explore_system import (
    ExploreSystem,
    BEHAVIOUR_NAME as BHVR_EXPLORE_SYSTEM,
)
from behaviours.monitor_cheapest_price import (
    MonitorPrices,
    BEHAVIOUR_NAME as BHVR_MONITOR_CHEAPEST_PRICE,
)
from behaviours.buy_and_deliver_or_sell import (
    BuyAndDeliverOrSell_6,
    BEHAVIOUR_NAME as BHVR_BUY_AND_DELIVER_OR_SELL,
)

from behaviours.receive_and_refine import (
    ReceiveAndRefine,
    BEHAVIOUR_NAME as BHVR_RECEIVE_AND_REFINE,
)
from behaviours.extract_and_fulfill import (
    ExtractAndFulfill_7,
    BEHAVIOUR_NAME as BHVR_EXTRACT_AND_FULFILL,
)

from behaviours.upgrade_ship_to_specs import (
    FindMountsAndEquip,
    BEHAVIOUR_NAME as BHVR_UPGRADE_TO_SPEC,
)
from behaviours.chill_and_survey import (
    ChillAndSurvey,
    BEHAVIOUR_NAME as BHVR_CHILL_AND_SURVEY,
)
from behaviours.refuel_all_fuel_exchanges_in_system import (
    RefuelAnExchange,
    BEHAVIOUR_NAME as BHVR_REFUEL_ALL_IN_SYSTEM,
)
from behaviours.single_stable_trade import (
    SingleStableTrade,
    BEHAVIOUR_NAME as BHVR_SINGLE_STABLE_TRADE,
)
from behaviours.monitor_specific_location import (
    MonitorPrices,
    BEHAVIOUR_NAME as BHVR_MONITOR_SPECIFIC_LOCATION,
)
from behaviours.take_from_extractors_and_fulfill import (
    TakeFromExactorsAndFulfillOrSell_9,
    BEHAVIOUR_NAME as BHVR_TAKE_FROM_EXTRACTORS_AND_FULFILL,
)
from behaviours.generic_behaviour import Behaviour
from straders_sdk.utils import try_execute_select, try_execute_upsert
from straders_sdk.pathfinder import PathFinder
from datetime import datetime, timedelta

BHVR_RECEIVE_AND_SELL = "RECEIVE_AND_SELL"
BHVR_EXTRACT_AND_TRANSFER_HIGHEST = "EXTRACT_AND_TRANSFER_HIGHEST"
BHVR_EXPLORE_CURRENT_SYSTEM = "EXPLORE_CURRENT_SYSTEM"
BHVR_EXTRACT_AND_TRANSFER_ALL = "EXTRACT_AND_TRANSFER_ALL"

behaviours_and_classes = {
    BHVR_EXTRACT_AND_GO_SELL: ExtractAndGoSell,
    BHVR_RECEIVE_AND_FULFILL: ReceiveAndFulfillOrSell_3,
    BHVR_EXTRACT_AND_TRANSFER: ExtractAndTransfer_8,
    # BHVR_REMOTE_SCAN_AND_SURV: RemoteScanWaypoints,
    BHVR_EXPLORE_SYSTEM: ExploreSystem,
    # BHVR_MONITOR_CHEAPEST_PRICE: MonitorPrices,
    BHVR_BUY_AND_DELIVER_OR_SELL: BuyAndSellDripfeed,
    # BHVR_EXTRACT_AND_FULFILL: ExtractAndFulfill_7,
    BHVR_RECEIVE_AND_REFINE: ReceiveAndRefine,
    BHVR_UPGRADE_TO_SPEC: FindMountsAndEquip,
    BHVR_CHILL_AND_SURVEY: ChillAndSurvey,
    BHVR_REFUEL_ALL_IN_SYSTEM: RefuelAnExchange,
    BHVR_SINGLE_STABLE_TRADE: SingleStableTrade,
    BHVR_BUY_AND_SELL_DRIPFEED: BuyAndSellDripfeed,
    BHVR_MONITOR_SPECIFIC_LOCATION: MonitorPrices,
    BHVR_EXTRACT_AND_CHILL: ExtractAndChill,
    BHVR_TAKE_FROM_EXTRACTORS_AND_FULFILL: TakeFromExactorsAndFulfillOrSell_9,
}

logger = logging.getLogger("dispatcher")


class dispatcher:
    def __init__(
        self,
        agents: list[tuple],
        db_host: str,
        db_port: str,
        db_name: str,
        db_user: str,
        db_pass: str,
    ) -> None:
        self.lock_id = f"{get_fun_name()}"
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.db_pass = db_pass
        self._connection = None
        self.connection_pool = []
        self.max_connections = 100
        self.last_connection = 0
        self.pathfinder = PathFinder(connection=self.connection)
        self.logger = logging.getLogger("dispatcher")
        self.agents = agents

        self.consumer = RequestConsumer(False)
        self.ships = {}
        self.tasks_last_updated = datetime.min
        self.task_refresh_period = timedelta(minutes=1)
        self.tasks = {}
        self.generic_behaviour = Behaviour("", "", connection=self.connection)
        self.client = self.generic_behaviour.st
        self.exit_flag = False

    def set_exit_flag(self, signum, frame):
        self.exit_flag = True
        self.logger.warning("Dispatcher received SIGINT, shutting down gracefully.")

    def get_unlocked_ships(self, current_agent_symbol: str) -> list[dict]:
        sql = """select s.ship_symbol, behaviour_id, locked_by, locked_until, behaviour_params
    from ships s 
    left join ship_behaviours sb 
    on s.ship_symbol = sb.ship_symbol

    where agent_name = %s
    and (locked_until <= (now() at time zone 'utc') or locked_until is null or locked_by = %s)
    order by last_updated asc """
        rows = try_execute_select(
            self.connection, sql, (current_agent_symbol, self.lock_id)
        )
        if not rows:
            return []
        return [
            {"name": row[0], "behaviour_id": row[1], "behaviour_params": row[4]}
            for row in rows
        ]

    def unlock_ship(self, connect, ship_symbol, lock_id):
        sql = """UPDATE ship_behaviours SET locked_by = null, locked_until = null
                WHERE ship_symbol = %s and locked_by = %s"""
        self.query(sql, (ship_symbol, lock_id))

    @property
    def connection(self):
        if self._connection is None or self._connection.closed > 0:
            self._connection = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_pass,
            )
            self._connection.autocommit = True
        return self._connection

    def get_connection(self):
        # switching this from a pool to just a connection generator that passes one connection down to the mediator (Which itself distributes it to the db and pg client)
        # generated connections appear to fail unpredictably during execution.
        # they seemed to be timing out / "closed unexpectedly" either immediately, or between surveys. Suspect keepalive shenanigans.

        return None
        new_con = psycopg2.connect(
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            user=self.db_user,
            password=self.db_pass,
            application_name=self.lock_id,
            # keepalives=1,
            # keepalives_idle=30,
            # keepalives_interval=10,
            # keepalives_count=3,  # connection terminates after 30 seconds of silence
        )

        return new_con

    def query(self, sql, args: list):
        return try_execute_select(self.connection, sql, args)

    def run(self):
        print(f"-----  DISPATCHER [{self.lock_id}] ACTIVATED ------")
        self.consumer.start()
        ships_and_threads: dict[str : threading.Thread] = {}
        check_frequency = timedelta(seconds=15 * len(self.agents))
        agents_and_last_checkeds = {}
        agents_and_unlocked_ships = {}
        self.client: SpaceTraders
        self.client.set_current_agent(self.agents[0][1], self.agents[0][0])
        self.client.ships_view(force=True)

        # rather than tying this behaviour to the probe, this is executed at the dispatcher level.

        ships_and_threads["scan_thread"] = threading.Thread(
            target=self.maybe_scan_all_systems, daemon=True
        )
        ships_and_threads["scan_thread"].start()
        startime = datetime.now()
        while not self.exit_flag:
            # if we've been running for more than 12 hours, terminate. important for profiling.
            #
            # every 15 seconds update the list of unlocked ships with a DB query
            #
            for token, agent_symbol in self.agents:
                self.client.current_agent_symbol = agent_symbol
                self.client.set_current_agent(agent_symbol, token)
                if (
                    agents_and_last_checkeds.get(
                        agent_symbol, datetime.now() - (check_frequency * 2)
                    )
                    + check_frequency
                    < datetime.now()
                ):
                    agents_and_unlocked_ships[agent_symbol] = self.get_unlocked_ships(
                        agent_symbol
                    )
                    agents_and_last_checkeds[agent_symbol] = datetime.now()
                    unlocked_ships = agents_and_unlocked_ships[agent_symbol]
                    active_ships = sum(
                        [1 for t in ships_and_threads.values() if t.is_alive()]
                    )

                    logging.info(
                        "dispatcher %s found %d unlocked ships for agent %s - %s active (%s%%)",
                        self.lock_id,
                        len(unlocked_ships),
                        agent_symbol,
                        active_ships,
                        round(active_ships / max(len(unlocked_ships), 1) * 100, 2),
                    )
                    if len(unlocked_ships) > 10:
                        set_logging(level=logging.INFO)
                        api_logger = logging.getLogger("API-Client")
                        api_logger.setLevel(logging.CRITICAL)
                        self.logger.level = logging.INFO
                        logging.getLogger().setLevel(logging.WARNING)
                        pass
                    # if we're running a ship and the lock has expired during execution, what do we do?
                    # do we relock the ship whilst we're running it, or terminate the thread
                    # I say terminate.

                #
                # check if we have idle ships whose behaviours we can execute.
                #

                for ship_and_behaviour in unlocked_ships:
                    if ship_and_behaviour["name"] in ships_and_threads:
                        thread = ships_and_threads[ship_and_behaviour["name"]]
                        thread: threading.Thread
                        if thread.is_alive():
                            continue
                        else:
                            del ships_and_threads[ship_and_behaviour["name"]]

                    #
                    # is there a task the ship can execute? if not, go to behaviour scripts instead.
                    #
                    task = self.get_task_for_ships(
                        self.client, ship_and_behaviour["name"]
                    )
                    if task:
                        if task["claimed_by"] is None or task["claimed_by"] == "":
                            self.claim_task(
                                task["task_hash"], ship_and_behaviour["name"]
                            )
                        task["behaviour_params"]["task_hash"] = task["task_hash"]
                        bhvr = self.map_behaviour_to_class(
                            task["behaviour_id"],
                            ship_and_behaviour["name"],
                            task["behaviour_params"],
                            agent_symbol,
                        )
                        doing_task = self.lock_and_execute(
                            ships_and_threads,
                            ship_and_behaviour["name"],
                            bhvr,
                            task["behaviour_id"],
                        )

                        if doing_task:
                            continue

                    #
                    # Instead, fallback behaviour.
                    #

                    # first time we've seen this ship - create a thread
                    bhvr = None
                    bhvr = self.map_behaviour_to_class(
                        ship_and_behaviour["behaviour_id"],
                        ship_and_behaviour["name"],
                        ship_and_behaviour["behaviour_params"],
                        agent_symbol,
                    )

                    self.lock_and_execute(
                        ships_and_threads,
                        ship_and_behaviour["name"],
                        bhvr,
                        ship_and_behaviour["behaviour_id"],
                    )
                    # time.sleep(min(10, 50 / len(ships_and_threads)))  # stagger ships
                    pass

                time.sleep(1)
        last_exec = False
        while (
            len([t for t in ships_and_threads.values() if t.is_alive()]) > 0
            or last_exec
        ):
            ships_to_pop = []
            last_exec = False
            for ship_id, thread in ships_and_threads.items():
                if not thread.is_alive():
                    thread.join()
                    print(f"ship {ship_id} has finished - releasing")
                    lock_ship(ship_id, self.lock_id, self.connection, duration=0)
                    ships_to_pop.append(ship_id)
            for ship_id in ships_to_pop:
                ships_and_threads.pop(ship_id)
                last_exec = len(ships_and_threads) == 0
            time.sleep(1)
        self.consumer.stop()

    def lock_and_execute(
        self, ships_and_threads: dict, ship_symbol: str, bhvr: Behaviour, bhvr_id
    ):
        if not bhvr:
            return False

        lock_r = lock_ship(ship_symbol, self.lock_id, self.connection)
        if lock_r is None:
            return False
        # we know this is behaviour, so lock it and start it.
        ships_and_threads[ship_symbol] = threading.Thread(
            target=bhvr.run,
            name=f"{ship_symbol}-{bhvr_id}",
        )
        self.logger.info("Starting thread for ship %s", ship_symbol)
        ships_and_threads[ship_symbol].start()
        return True

    def claim_task(self, task_hash, ship_symbol):
        sql = """
            UPDATE public.ship_tasks
	        SET  claimed_by= %s
	        WHERE task_hash = %s;"""
        try_execute_upsert(self.connection, sql, (ship_symbol, task_hash))
        pass

    def get_task_for_ships(self, client: SpaceTraders, ship_symbol):
        if self.tasks_last_updated + self.task_refresh_period < datetime.now():
            sql = """SELECT task_hash, agent_symbol, requirements, expiry, priority, claimed_by, behaviour_id, target_system, behaviour_params, completed
 
            from ship_tasks
                where (completed is null or completed is false)
                and (claimed_by is null 
                or claimed_By = %s)
                and (agent_symbol = %s or agent_symbol is null)
                and (expiry > now() at time zone 'utc' or expiry is null)
                order by claimed_by, priority;

                """
            results = try_execute_select(
                self.connection, sql, (ship_symbol, client.current_agent_symbol)
            )
            self.tasks = {
                row[0]: {
                    "task_hash": row[0],
                    "agent_symbol": row[1],
                    "requirements": row[2],
                    "expiry": row[3],
                    "priority": row[4],
                    "claimed_by": row[5],
                    "behaviour_id": row[6],
                    "target_system": row[7],
                    "behaviour_params": row[8],
                }
                for row in results
            }
        ship = self.ships.get(ship_symbol, None)
        if not ship:
            ship = client.ships_view_one(ship_symbol)
            if not ship:
                self.logger.warning(
                    "For some reason the ship %s doesn't exist in db", ship_symbol
                )
                return None
            self.ships[ship_symbol] = ship

        for hash, task in self.tasks.items():
            if task["claimed_by"] == ship_symbol:
                return task
        valid_tasks = []
        #
        # get all the highest priority tasks.
        #
        highest_priority = 999999
        shortest_distance = 999999
        for hash, task in self.tasks.items():
            if task["claimed_by"] is None:
                valid_for_ship = True
                if task["requirements"]:
                    for requirement in task["requirements"]:
                        if requirement == "DRONE" and ship.frame.symbol not in [
                            "FRAME_DRONE",
                            "FRAME_PROBE",
                        ]:
                            valid_for_ship = False
                            break
                        if requirement == "EXPLORER" and ship.role != "COMMANDER":
                            valid_for_ship = False
                            break
                        if (
                            requirement == "HEAVY_FREIGHTER"
                            and ship.role != "HAULER"
                            and ship.cargo_capacity >= 360
                        ):
                            valid_for_ship = False
                            break
                        if "_CARGO" in requirement and ship.cargo_capacity < int(
                            re.findall(r"\d+", requirement)[0]
                        ):
                            valid_for_ship = False
                            break
                if valid_for_ship:
                    if task["priority"] < highest_priority:
                        highest_priority = task["priority"]
                        valid_tasks = []
                        # reset the list, discard lower priorities from consideration.

                    valid_tasks.append(task)
            else:
                continue
        best_task = None
        start_system = client.systems_view_one(ship.nav.system_symbol)
        for task in valid_tasks:
            end_system = client.systems_view_one(task["target_system"])
            try:
                path = self.pathfinder.astar(start_system, end_system)
            except Exception as err:
                self.logger.error("Couldn't find path because %s", err)
                path = []
            if path and len(path) < shortest_distance:
                shortest_distance = len(path)
                best_task = task

        return best_task
        # does this ship meet the requirements? not currently implemented

    def map_behaviour_to_class(
        self, behaviour_id: str, ship_symbol: str, behaviour_params: dict, aname
    ) -> Behaviour:
        id = behaviour_id
        sname = ship_symbol
        bhvr_params = behaviour_params
        bhvr = None
        if id in behaviours_and_classes:
            bhvr = behaviours_and_classes[id](aname, sname, bhvr_params)
            return bhvr

    def maybe_scan_all_systems(self):
        st = self.client
        sql = """select count(distinct system_symbol) from systems"""
        row = try_execute_select(self.connection, sql, [])
        status = st.game_status()

        api_systems = status.total_systems
        got_em_all = row[0][0] == api_systems

        agent = st.view_my_self()
        headquarters = agent.headquarters
        hq_system = st.systems_view_one(waypoint_slicer(headquarters), True)
        for waypoint in hq_system.waypoints:
            waypoint = st.waypoints_view_one(hq_system.symbol, waypoint.symbol)
            if not waypoint:
                continue
            if len(waypoint.traits) == 0 or waypoint.type == "JUMP_GATE":
                # refresh the traits
                waypoint = st.waypoints_view_one(
                    hq_system.symbol, waypoint.symbol, True
                )
            traits = [trait.symbol for trait in waypoint.traits]
            if "SHIPYARD" in traits:
                st.system_shipyard(waypoint)
            if "MARKETPLACE" in traits:
                st.system_market(waypoint)
            if waypoint.type == "JUMP_GATE":
                st.system_jumpgate(waypoint)

        return
        if got_em_all:
            return
        for i in range(1, math.ceil(api_systems / 20) + 1):
            print(i)
            resp = st.systems_view_twenty(i, True)
            while not resp:
                time.sleep(20)
                resp = st.systems_view_twenty(i, True)
                self.logger.warn("Failed to get system - page %s - retrying", i)
            if not resp:
                self.logger.error(
                    "Failed to get system - page %s - redo this later!", i
                )
            time.sleep(1.2)


def get_fun_name():
    prefixes = ["shadow", "crimson", "midnight", "dark", "mercury", "crimson", "black"]
    mid_parts = [
        "fall",
        "epsilon",
        "omega",
        "phoenix",
        "pandora",
        "serpent",
        "zephyr",
        "tide",
        "sun",
        "nebula",
        "horizon",
        "rose",
        "nova",
        "weaver",
        "sky",
        "titan",
        "helios",
    ]
    suffixes = ["five", "seven", "nine", "prime"]
    prefix_index = random.randint(0, len(mid_parts) - 1)
    mid_index = random.randint(0, len(mid_parts) - 1)
    suffix_index = random.randint(0, len(mid_parts) - 1)
    prefix = f"{prefixes[prefix_index]} " if prefix_index < len(prefixes) else ""
    mid = mid_parts[mid_index]
    suffix = f" {suffixes[suffix_index]}" if suffix_index < len(suffixes) else ""

    return f"{prefix}{mid}{suffix}".lower()


def register_and_store_user(username) -> str:
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
    return resp.data["token"]


def load_users(username=None) -> list[tuple]:
    try:
        user = json.load(open("user.json", "r"))
    except FileNotFoundError:
        register_and_store_user(username)
        return

    if username:
        for agent in user["agents"]:
            if agent["username"] == username:
                return [(agent["token"], agent["username"])]
        resp = register_and_store_user(username)

        if resp:
            return load_users(username)
    else:
        resp_obj = []
        for agent in user["agents"]:
            if "token" in agent and "username" in agent:
                resp_obj.append((agent["token"], agent["username"]))
        return resp_obj

    logging.error("Could neither load nor register user %s", username)


def lock_ship(ship_symbol, lock_id, connection, duration=60):
    sql = """INSERT INTO ship_behaviours (ship_symbol, locked_by, locked_until)
    VALUES (%s, %s, (now() at time zone 'utc') + interval '%s minutes')
    ON CONFLICT (ship_symbol) DO UPDATE SET
        locked_by = %s,
        locked_until = (now() at time zone 'utc') + interval '%s minutes';"""

    return try_execute_upsert(
        connection, sql, (ship_symbol, lock_id, duration, lock_id, duration)
    )


if __name__ == "__main__":
    target_user = None
    if len(sys.argv) >= 2:
        # no username provided, dispatch for all locally saved agents. (TERRIBLE IDEA GENERALLY)
        target_user = sys.argv[1].upper()

    set_logging(level=logging.DEBUG)
    users = load_users(target_user)
    dips = dispatcher(
        users,
        os.environ.get("ST_DB_HOST", "DB_HOST_not_set"),
        os.environ.get("ST_DB_PORT", "DB_PORT_not_set"),
        os.environ.get("ST_DB_NAME", "DB_NAME_not_set"),
        os.environ.get("ST_DB_USER", "DB_USER_not_set"),
        os.environ.get("ST_DB_PASSWORD", "DB_PASSWORD_not_set"),
    )
    signal.signal(signal.SIGINT, dips.set_exit_flag)
    dips.run()
    exit()
    ships = dips.ships_view(True)
    hq_sys = list(dips.ships_view().values())[1].nav.system_symbol
    hq_sym = dips.current_agent.headquarters

    hq = dips.waypoints_view_one(hq_sys, hq_sym)
    # home_wapys = dips.waypoints_view(hq_sys, True)
    hq: Waypoint
    if len(hq.traits) == 0:
        dips.waypoints_view(hq_sys, True)
    pytest_blob = {
        "token": dips.token,
        "hq_sys": hq_sys,
        "hq_wayp": list(ships.values())[1].nav.waypoint_symbol,
        "market_wayp": dips.find_waypoints_by_trait_one(hq_sys, "MARKETPLACE").symbol,
        "shipyard_wayp": dips.find_waypoints_by_trait_one(hq_sys, "SHIPYARD").symbol,
    }
    print(json.dumps(pytest_blob, indent=2))

    dips.run()
    # need to assign default behaviours here.

    # get unlocked ships with behaviours
    # unlocked_ships = [{"name": "ship_id", "behaviour_id": "EXTRACT_AND_SELL"}]
