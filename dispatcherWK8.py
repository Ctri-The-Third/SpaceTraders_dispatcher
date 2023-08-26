# this is the ship dispatcher / conductor script.
# It will get unlocked ships from the DB, check their behaviour ID and if it matches a known behaviour, lock the ship and execute the behaviour.
import json
import logging
import psycopg2
import sys, threading, os, uuid, time
from requests_ratelimiter import LimiterSession
from straders_sdk.models import Agent
from straders_sdk import SpaceTraders
from straders_sdk.models import Waypoint
from straders_sdk.utils import set_logging
from behaviours.extract_and_sell import ExtractAndSell
from behaviours.receive_and_fulfill import ReceiveAndFulfillOrSell_3
from behaviours.generic_behaviour import Behaviour
import random
from pyrate_limiter import Limiter, Duration, RequestRate
from behaviours.extract_and_transfer_or_sell import (
    ExtractAndTransferOrSell_4,
    BEHAVIOUR_NAME as BHVR_EXTRACT_AND_TRANSFER_OR_SELL,
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
from behaviours.generic_behaviour import Behaviour
from straders_sdk.utils import try_execute_select, try_execute_upsert
from datetime import datetime, timedelta

BHVR_EXTRACT_AND_SELL = "EXTRACT_AND_SELL"
BHVR_RECEIVE_AND_SELL = "RECEIVE_AND_SELL"
BHVR_EXTRACT_AND_TRANSFER_HIGHEST = "EXTRACT_AND_TRANSFER_HIGHEST"
BHVR_RECEIVE_AND_FULFILL = "RECEIVE_AND_FULFILL"
BHVR_EXPLORE_CURRENT_SYSTEM = "EXPLORE_CURRENT_SYSTEM"
BHVR_EXTRACT_AND_TRANSFER_ALL = "EXTRACT_AND_TRANSFER_ALL"


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
        self.lock_id = f"w5dis {get_fun_name()}"
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.db_pass = db_pass
        self._connection = None
        self.logger = logging.getLogger("dispatcher")
        self.agents = agents

        self.session = LimiterSession(per_second=3)

    def get_unlocked_ships(self, current_agent_symbol: str) -> list[dict]:
        sql = """select s.ship_symbol, behaviour_id, locked_by, locked_until, behaviour_params
    from ships s 
    left join ship_behaviours sb 
    on s.ship_symbol = sb.ship_symbol

    where agent_name = %s
    and (locked_until <= (now() at time zone 'utc') or locked_until is null or locked_by = %s)
    order by last_updated asc """
        rows = self.query(sql, (current_agent_symbol, self.lock_id))

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

    def query(self, sql, args: list):
        return try_execute_select(self.connection, sql, args)

    def run(self):
        print(f"-----  DISPATCHER [{self.lock_id}] ACTIVATED ------")

        ships_and_threads: dict[str : threading.Thread] = {}
        check_frequency = timedelta(seconds=15 * len(self.agents))
        agents_and_last_checkeds = {}
        agents_and_unlocked_ships = {}
        while True:
            #
            # every 15 seconds update the list of unlocked ships with a DB query
            #
            for _, agent_symbol in self.agents:
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
                        # set_logging(level=logging.INFO)
                        # api_logger = logging.getLogger("API-Client")
                        # api_logger.setLevel(logging.INFO)
                        # self.logger.level = logging.INFO
                        # logging.getLogger().setLevel(logging.INFO)
                        pass
                    # if we're running a ship and the lock has expired during execution, what do we do?
                    # do we relock the ship whilst we're running it, or terminate the thread
                    # I say terminate.

                #
                # check if we have idle ships whose behaviours we can execute.
                #

                for ship_and_behaviour in unlocked_ships:
                    # are we already running this behaviour?

                    if ship_and_behaviour["name"] in ships_and_threads:
                        thread = ships_and_threads[ship_and_behaviour["name"]]
                        thread: threading.Thread
                        if thread.is_alive():
                            continue
                        else:
                            del ships_and_threads[ship_and_behaviour["name"]]

                    # first time we've seen this ship - create a thread
                    bhvr = None
                    bhvr = self.map_behaviour_to_class(
                        ship_and_behaviour["behaviour_id"],
                        ship_and_behaviour["name"],
                        ship_and_behaviour["behaviour_params"],
                        agent_symbol,
                    )

                    if not bhvr:
                        continue

                    lock_r = lock_ship(
                        ship_and_behaviour["name"], self.lock_id, self.connection
                    )
                    if lock_r is None:
                        continue
                    # we know this is behaviour, so lock it and start it.
                    ships_and_threads[ship_and_behaviour["name"]] = threading.Thread(
                        target=bhvr.run,
                        name=f"{ship_and_behaviour['name']}-{ship_and_behaviour['behaviour_id']}",
                    )
                    self.logger.info(
                        "Starting thread for ship %s", ship_and_behaviour["name"]
                    )
                    ships_and_threads[ship_and_behaviour["name"]].start()
                    # time.sleep(min(10, 50 / len(ships_and_threads)))  # stagger ships
                    pass

                time.sleep(1)

    def map_behaviour_to_class(
        self, behaviour_id: str, ship_symbol: str, behaviour_params: dict, aname
    ) -> Behaviour:
        id = behaviour_id
        sname = ship_symbol
        bhvr_params = behaviour_params
        bhvr = None
        if id == BHVR_EXTRACT_AND_SELL:
            bhvr = ExtractAndSell(aname, sname, bhvr_params, session=self.session)
        elif id == BHVR_RECEIVE_AND_FULFILL:
            bhvr = ReceiveAndFulfillOrSell_3(
                aname, sname, behaviour_params, session=self.session
            )
        elif id == BHVR_EXTRACT_AND_TRANSFER_OR_SELL:
            bhvr = ExtractAndTransferOrSell_4(
                aname, sname, bhvr_params, session=self.session
            )
        elif id == BHVR_REMOTE_SCAN_AND_SURV:
            bhvr = RemoteScanWaypoints(aname, sname, bhvr_params, session=self.session)
        elif id == BHVR_EXPLORE_SYSTEM:
            bhvr = ExploreSystem(aname, sname, bhvr_params, session=self.session)
        elif id == BHVR_MONITOR_CHEAPEST_PRICE:
            bhvr = MonitorPrices(aname, sname, bhvr_params, session=self.session)
        elif id == BHVR_BUY_AND_DELIVER_OR_SELL:
            bhvr = BuyAndDeliverOrSell_6(
                aname, sname, bhvr_params, session=self.session
            )
        else:
            pass
        return bhvr


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
