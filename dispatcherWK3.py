# this is the ship dispatcher / conductor script.
# It will get unlocked ships from the DB, check their behaviour ID and if it matches a known behaviour, lock the ship and execute the behaviour.
import json
import logging
import psycopg2
import os
import uuid
from spacetraders_v2 import SpaceTraders
from spacetraders_v2.models import Waypoint
import sys
from spacetraders_v2.utils import set_logging
import threading
from behaviours.extract_and_sell import ExtractAndSell
import time

BHVR_EXTRACT_AND_SELL = "EXTRACT_AND_SELL"
BHVR_RECEIVE_AND_SELL = "RECEIVE_AND_SELL"
BHVR_EXTRACT_AND_TRANSFER = "EXTRACT_AND_TRANSFER"
BHVR_RECEIVE_AND_FULFILL = "RECEIVE_AND_FULFILL"
BHVR_EXPLORE_CURRENT_SYSTEM = "EXPLORE_CURRENT_SYSTEM"

logger = logging.getLogger("dispatcher")


class dispatcher(SpaceTraders):
    def __init__(
        self,
        token,
        db_host: str,
        db_port: str,
        db_name: str,
        db_user: str,
        db_pass: str,
        current_agent_symbol: str,
    ) -> None:
        self.lock_id = "Week3-dispatcher " + str(uuid.uuid1())
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.db_pass = db_pass
        self._connection = None
        super().__init__(
            token,
            db_host=db_host,
            db_port=db_port,
            db_name=db_name,
            db_user=db_user,
            db_pass=db_pass,
            current_agent_symbol=current_agent_symbol,
        )

        self.agent = self.view_my_self()
        self.ships = self.ships_view()

    def get_unlocked_ships(self, current_agent_symbol: str) -> list[dict]:
        sql = """select s.ship_symbol, behaviour_id, locked_by, locked_until 
    from ship s 
    left join ship_behaviours sb 
    on s.ship_symbol = sb.ship_name

    where agent_name = %s
    and (locked_until <= now() or locked_until is null or locked_by = %s)
    order by last_updated asc """
        rows = self.query(sql, (current_agent_symbol, self.lock_id))

        return [{"name": row[0], "behaviour_id": row[1]} for row in rows]

    def lock_ship(self, ship_name, lock_id):
        sql = """INSERT INTO ship_behaviours (ship_name, locked_by, locked_until)
    VALUES (%s, %s, now() + interval '60 minutes')
    ON CONFLICT (ship_name) DO UPDATE SET
        locked_by = %s,
        locked_until = now() + interval '15 minutes';"""

        return self.query(sql, (ship_name, lock_id, lock_id))

    def unlock_ship(self, connect, ship_name, lock_id):
        sql = """UPDATE ship_behaviours SET locked_by = null, locked_until = null
                WHERE ship_name = %s and locked_by = %s"""
        self.query(sql, (ship_name, lock_id))

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
        for int in range(0, 5):
            try:
                cur = self.connection.cursor()
                cur.execute(sql, args)
                return cur.fetchall()
            except psycopg2.ProgrammingError as err:
                return []
            except Exception as err:
                logger.error("could not execute %s because %s", sql, err)
                time.sleep((int + 1) * int)
                return None

        return []

    def run(self):
        ships_and_threads: dict[str : threading.Thread] = {}

        while True:
            # every 15 seconds update the list of unlocked ships with a DB query.

            unlocked_ships = self.get_unlocked_ships(self.agent.symbol)
            logging.debug(" found %d unlocked ships", len(unlocked_ships))
            # every second, check if we have idle ships whose behaviours we can execute.
            for i in range(15):
                for ship_and_behaviour in unlocked_ships:
                    # are we already running this behaviour?

                    if ship_and_behaviour["name"] in ships_and_threads:
                        thread = ships_and_threads[ship_and_behaviour["name"]]
                        thread: threading.Thread
                        if thread.is_alive():
                            continue
                        else:
                            # the thread is dead, so unlock the ship and remove it from the list
                            self.unlock_ship(
                                self.connection,
                                ship_and_behaviour["name"],
                                self.lock_id,
                            )
                            del ships_and_threads[ship_and_behaviour["name"]]
                    else:
                        # first time we've seen this ship - create a thread
                        pass
                    bhvr = None
                    behaviour_params: dict = ({},)

                    if ship_and_behaviour["behaviour_id"] == BHVR_EXTRACT_AND_SELL:
                        bhvr = ExtractAndSell(
                            self.agent.symbol, ship_and_behaviour["name"]
                        )

                    if not bhvr:
                        continue

                    lock_r = self.lock_ship(ship_and_behaviour["name"], self.lock_id)
                    if lock_r is None:
                        continue
                    # we know this is behaviour, so lock it and start it.
                    ships_and_threads[ship_and_behaviour["name"]] = threading.Thread(
                        target=bhvr.run,
                        name=f"{ship_and_behaviour['name']}-{ship_and_behaviour['behaviour_id']}",
                    )

                    ships_and_threads[ship_and_behaviour["name"]].start()
                    time.sleep(10)  # stagger ships
                    pass

                time.sleep(1)


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


def load_user(username):
    try:
        user = json.load(open("user.json", "r"))
    except FileNotFoundError:
        register_and_store_user(username)
        register_and_store_user(username)
        return
    for agent in user["agents"]:
        if agent["username"] == username:
            return agent["token"], agent["username"]
    register_and_store_user(username)
    return load_user(username)


if __name__ == "__main__":
    target_user = sys.argv[1].upper()

    set_logging(level=logging.DEBUG)
    user = load_user(target_user)

    dips = dispatcher(
        user[0],
        os.environ.get("ST_DB_HOST"),
        os.environ.get("ST_DB_PORT"),
        os.environ.get("ST_DB_NAME"),
        os.environ.get("ST_DB_USER"),
        os.environ.get("ST_DB_PASSWORD"),
        user[1],
    )

    ships = dips.ships_view(True)
    hq_sys = list(dips.ships_view().values())[1].nav.system_symbol
    hq = dips.waypoints_view_one(hq_sys, dips.current_agent.headquaters)
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
