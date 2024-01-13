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
from straders_sdk.pg_connection_pool import PGConnectionPool
from straders_sdk.models import Waypoint
from straders_sdk.utils import set_logging, waypoint_slicer, get_and_validate
from straders_sdk.utils import get_name_from_token

from behaviours.scan_behaviour import ScanInBackground
from behaviours.generic_behaviour import Behaviour
from straders_sdk.utils import try_execute_select, try_execute_upsert
from straders_sdk.pathfinder import PathFinder
from datetime import datetime, timedelta

RQ_DRONE = "REQUIRE_DRONE"
RQ_EXPLORER = "EXPLORER"
RQ_HEAVY_FREIGHTER = "HEAVY_FREIGHTER"
RQ_ANY_FREIGHTER = "ANY_FREIGHTER"
RQ_CARGO = "_CARGO"
RQ_FUEL = "_FUEL"

from behaviour_constants import *
from behaviour_constants import behaviours_and_classes

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
        self.connection_pool = PGConnectionPool(
            db_user, db_pass, db_host, db_name, db_port
        )
        self.pathfinder = PathFinder()
        self.logger = logging.getLogger("dispatcher")
        self.agents = agents

        self.consumer = RequestConsumer(False)
        self.ships = {}
        self.tasks_last_updated = datetime.min
        self.task_refresh_period = timedelta(minutes=1)
        self.tasks = {}
        self.generic_behaviour = Behaviour("", "")
        self.client = self.generic_behaviour.st
        self.exit_flag = False
        self.connection = self.connection_pool.get_connection()

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
            sql, (current_agent_symbol, self.lock_id), self.connection
        )
        if not rows:
            return []
        return [
            {"name": row[0], "behaviour_id": row[1], "behaviour_params": row[4]}
            for row in rows
        ]

    def unlock_ship(self, ship_symbol, lock_id):
        sql = """UPDATE ship_behaviours SET locked_by = null, locked_until = null
                WHERE ship_symbol = %s and locked_by = %s"""
        try_execute_upsert(sql, (ship_symbol, lock_id), self.connection)

    def query(self, sql, args: list):
        return try_execute_select(sql, args)

    def run(self):
        print(f"-----  DISPATCHER [{self.lock_id}] ACTIVATED ------")
        self.consumer.start()
        ships_and_threads: dict[str : threading.Thread] = {}

        self.client: SpaceTraders
        self.client.set_current_agent(self.agents[0][1], self.agents[0][0])
        self.client.ships_view(force=True)

        # rather than tying this behaviour to the probe, this is executed at the dispatcher level.

        scan_thread = threading.Thread(target=self.maybe_scan_all_systems, daemon=True)
        scan_thread.start()
        # ships_and_threads["scan_thread"].start()
        startime = datetime.now()
        while not self.exit_flag:
            self._the_big_loop(ships_and_threads)
        #            try:
        #                self._the_big_loop(ships_and_threads)
        #            except Exception as err:
        #                self.logger.error("Error in the big loop: %s", err)
        #                self.st.sleep(30)

        last_exec = False
        while (
            len([t for t in ships_and_threads.values() if t.is_alive()]) > 0
            or last_exec
        ):
            ships_to_pop = []

            for ship_id, thread in ships_and_threads.items():
                if not thread.is_alive():
                    thread.join()
                    print(f"ship {ship_id} has finished - releasing")
                    lock_ship(ship_id, self.lock_id, duration=0)
                    ships_to_pop.append(ship_id)

            for ship_id in ships_to_pop:
                ships_and_threads.pop(ship_id)
                last_exec = len(ships_and_threads) == 0
            self.client.sleep(1)
        # release the final ship
        for ship_id, thread in ships_and_threads.items():
            if not thread.is_alive():
                thread.join()
                print(f"FINAL RELEASE - ship {ship_id} has finished - releasing")
                lock_ship(ship_id, self.lock_id, duration=0)

        self.consumer.stop()

    def _the_big_loop(self, ships_and_threads):
        agents_and_last_checkeds = {}
        agents_and_unlocked_ships = {}
        check_frequency = timedelta(seconds=15 * len(self.agents))

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
                    "dispatcher %s found %d unlocked ships for agent %s - %s active (%s%%). Request consumer is_alive? %s",
                    self.lock_id,
                    len(unlocked_ships),
                    agent_symbol,
                    active_ships,
                    round(active_ships / max(len(unlocked_ships), 1) * 100, 2),
                    self.consumer._consumer_thread.is_alive(),
                )
                if False:
                    if len(unlocked_ships) > 10:
                        set_logging(level=logging.INFO)
                        consumer_logger = logging.getLogger("RequestConsumer")
                        consumer_logger.setLevel(logging.CRITICAL)
                        api_logger = logging.getLogger("API-Client")
                        api_logger.setLevel(logging.CRITICAL)
                        self.logger.level = logging.INFO
                        logging.getLogger().setLevel(logging.INFO)
                        pass
                # if we're running a ship and the lock has expired during execution, what do we do?
                # do we relock the ship whilst we're running it, or terminate the thread
                # I say terminate.

            #
            # check if we have idle ships whose behaviours we can execute.
            #

            for ship_and_behaviour in unlocked_ships:
                ship_name = ship_and_behaviour["name"]
                if ship_name in ships_and_threads:
                    thread = ships_and_threads[ship_name]
                    thread: threading.Thread
                    if thread.is_alive():
                        continue
                    else:
                        del ships_and_threads[ship_name]

                #
                # is there a task the ship can execute? if not, go to behaviour scripts instead.
                #
                task = self.get_task_for_ships(self.client, ship_name)
                if task:
                    if task["claimed_by"] is None or task["claimed_by"] == "":
                        self.claim_task(task["task_hash"], ship_name)
                    task["behaviour_params"]["task_hash"] = task["task_hash"]

                    bhvr = self.map_behaviour_to_class(
                        task["behaviour_id"],
                        ship_name,
                        task["behaviour_params"],
                        agent_symbol,
                    )
                    doing_task = self.lock_and_execute(
                        ships_and_threads,
                        ship_name,
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
                    ship_name,
                    ship_and_behaviour["behaviour_params"],
                    agent_symbol,
                )

                self.lock_and_execute(
                    ships_and_threads,
                    ship_name,
                    bhvr,
                    ship_and_behaviour["behaviour_id"],
                )
                # self.client.sleep(min(10, 50 / len(ships_and_threads)))  # stagger ships
                pass

            self.client.sleep(1)

    def lock_and_execute(
        self, ships_and_threads: dict, ship_symbol: str, bhvr: Behaviour, bhvr_id
    ):
        if not bhvr:
            return False

        lock_r = lock_ship(ship_symbol, self.lock_id, connection=self.connection)
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
        try_execute_upsert(sql, (ship_symbol, task_hash))
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
                sql, (ship_symbol, client.current_agent_symbol), self.connection
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
                        if requirement == RQ_DRONE and ship.frame.symbol not in [
                            "FRAME_DRONE",
                            "FRAME_PROBE",
                        ]:
                            valid_for_ship = False
                            break
                        if requirement == RQ_EXPLORER and ship.role != "COMMANDER":
                            valid_for_ship = False
                            break
                        if (
                            requirement == RQ_HEAVY_FREIGHTER
                            and ship.role != "HAULER"
                            and ship.cargo_capacity >= 360
                        ):
                            valid_for_ship = False
                            break
                        if requirement == RQ_ANY_FREIGHTER and ship.role not in (
                            "HAULER",
                            "COMMAND",
                        ):
                            valid_for_ship = False
                            break

                        if RQ_CARGO in requirement and ship.cargo_capacity < int(
                            re.findall(r"\d+", requirement)[0]
                        ):
                            valid_for_ship = False
                            break

                        if RQ_FUEL in requirement and ship.fuel_capacity < int(
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
        ships = self.client.ships_view()
        ship = list(ships.values())[0]
        bhvr = ScanInBackground(
            self.client.current_agent_symbol, ship.name, {"priority": 10}
        )
        bhvr.run()


def get_fun_name():
    prefixes = ["shadow", "crimson", "midnight", "dark", "mercury", "crimson", "black"]
    mid_parts = [
        "fall",
        "epsilon",
        "omega",
        "phoenix",
        "pandora",
        "squirrel",
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

    wait_until_reset("https://api.spacetraders.io/v2/", user)

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


def wait_until_reset(url, user_file: dict):
    target_date = user_file["reset_date"]
    current_reset_date = "1990-01-01"
    while target_date != current_reset_date:
        response = get_and_validate(url)
        try:
            if (
                response.status_code == 200
                and response.response_json["resetDate"] == target_date
            ):
                return
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
            time.sleep(5)


def lock_ship(ship_symbol, lock_id, duration=60, connection=None):
    sql = """INSERT INTO ship_behaviours (ship_symbol, locked_by, locked_until)
    VALUES (%s, %s, (now() at time zone 'utc') + interval '%s minutes')
    ON CONFLICT (ship_symbol) DO UPDATE SET
        locked_by = %s,
        locked_until = (now() at time zone 'utc') + interval '%s minutes';"""

    return try_execute_upsert(
        sql, (ship_symbol, lock_id, duration, lock_id, duration), connection
    )


if __name__ == "__main__":
    target_user = None
    if len(sys.argv) >= 2:
        # no username provided, dispatch for all locally saved agents. (TERRIBLE IDEA GENERALLY)
        target_user = sys.argv[1].upper()
        users = load_users(target_user)

    set_logging(level=logging.DEBUG)
    if not target_user:
        # no username provided, check for a token in the environment variables
        token = os.environ.get("ST_TOKEN", None)
        if not token:
            logging.error("env variable ST_TOKEN is not set. Exiting.")
            exit()

        user = get_name_from_token(token)
        if user:
            users = [(token, user)]
    try:
        dips = dispatcher(
            users,
            os.environ.get("ST_DB_HOST", "ST_DB_HOST_not_set"),
            os.environ.get("ST_DB_PORT", None),
            os.environ.get("ST_DB_NAME", "ST_DB_NAME_not_set"),
            os.environ.get("ST_DB_USER", "ST_DB_USER_not_set"),
            os.environ.get("ST_DB_PASSWORD", "DB_PASSWORD_not_set"),
        )
        signal.signal(signal.SIGINT, dips.set_exit_flag)
    except Exception as err:
        logging.error("%s", err)
        time.sleep(60 * 10)
        exit()
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
