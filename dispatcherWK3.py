# this is the ship dispatcher / conductor script.
# It will get unlocked ships from the DB, check their behaviour ID and if it matches a known behaviour, lock the ship and execute the behaviour.
import json
import logging
import psycopg2
import uuid
from spacetraders_v2 import SpaceTraders
from spacetraders_v2.utils import set_logging
import threading
from behaviours.extract_and_sell import ExtractAndSell
import time

BHVR_EXTRACT_AND_SELL = "EXTRACT_AND_SELL"
BHVR_RECEIVE_AND_SELL = "RECEIVE_AND_SELL"
BHVR_EXTRACT_AND_TRANSFER = "EXTRACT_AND_TRANSFER"
BHVR_RECEIVE_AND_FULFILL = "RECEIVE_AND_FULFILL"
BHVR_EXPLORE_CURRENT_SYSTEM = "EXPLORE_CURRENT_SYSTEM"


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
        logging.error(
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


def get_unlocked_ships(connection, current_agent_symbol: str) -> list[dict]:
    cur = connection.cursor()
    sql = """select s.ship_symbol, behaviour_id, locked_by, locked_until 
from ship s 
left join ship_behaviours sb 
on s.ship_symbol = sb.ship_name

where agent_name = %s
and (locked_until <= now() or locked_until is null or locked_by = %s)
order by last_updated asc """
    try:
        cur.execute(sql, (current_agent_symbol, current_agent_symbol))
        rows = cur.fetchall()
    except Exception as err:
        logging.error("could not get unlocked ships becase %s", err)
        return []

    return [{"name": row[0], "behaviour_id": row[1]} for row in rows]


def lock_ship(connection, ship_name, lock_id):
    sql = """INSERT INTO ship_behaviours (ship_name, locked_by, locked_until)
VALUES (%s, %s, now() + interval '60 minutes')
ON CONFLICT (ship_name) DO UPDATE SET
    locked_by = %s,
    locked_until = now() + interval '15 minutes';"""
    try:
        cur = connection.cursor()
        cur.execute(sql, (ship_name, lock_id, lock_id))
        return True
    except Exception as err:
        logging.error("could not lock ship %s because %s", ship_name, err)
        return False


def unlock_ship(connect, ship_name, lock_id):
    sql = """UPDATE ship_behaviours SET locked_by = null, locked_until = null
            WHERE ship_name = %s and locked_by = %s"""
    try:
        cur = connection.cursor()
        cur.execute(sql, (ship_name, lock_id))
        return True
    except Exception as err:
        logging.error("could not unlock ship %s because %s", ship_name, err)
        return False


if __name__ == "__main__":
    register_and_store_user("O2O")
    set_logging()
    lock_id = "Week3-dispatcher " + str(uuid.uuid1())
    user = json.load(open("user.json", "r"))
    st = SpaceTraders(
        user["agents"][0]["token"],
        db_host=user["db_host"],
        db_port=user["db_port"],
        db_name=user["db_name"],
        db_user=user["db_user"],
        db_pass=user["db_pass"],
        current_agent_symbol=user["agents"][1]["username"],
    )
    agent = st.view_my_self()
    ships = st.ships_view()
    hq_sys = list(ships.values())[1].nav.system_symbol

    pytest_blob = {
        "token": st.token,
        "hq_sys": hq_sys,
        "hq_wayp": list(ships.values())[1].nav.waypoint_symbol,
        "market_wayp": st.find_waypoints_by_trait_one(hq_sys, "MARKETPLACE").symbol,
        "shipyard_wayp": st.find_waypoints_by_trait_one(hq_sys, "SHIPYARD").symbol,
    }
    print(json.dumps(pytest_blob, indent=2))

    connection = psycopg2.connect(
        host=user["db_host"],
        port=user["db_port"],
        database=user["db_name"],
        user=user["db_user"],
        password=user["db_pass"],
    )
    connection.autocommit = True

    ships_and_threads: dict[str : threading.Thread] = {}

    # need to assign default behaviours here.

    # get unlocked ships with behaviours
    # unlocked_ships = [{"name": "ship_id", "behaviour_id": "EXTRACT_AND_SELL"}]
    while True:
        # every 15 seconds update the list of unlocked ships with a DB query.
        unlocked_ships = get_unlocked_ships(connection, agent.symbol)
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
                        unlock_ship(connection, ship_and_behaviour["name"], lock_id)
                        del ships_and_threads[ship_and_behaviour["name"]]
                bhvr = None
                behaviour_params: dict = ({},)

                match ship_and_behaviour["behaviour_id"]:
                    case BHVR_EXTRACT_AND_SELL:
                        bhvr = ExtractAndSell(agent.symbol, ship_and_behaviour["name"])

                if not bhvr:
                    continue

                if not lock_ship(connection, ship_and_behaviour["name"], lock_id):
                    continue
                # we know this is behaviour, so lock it and start it.
                ships_and_threads[ship_and_behaviour["name"]] = threading.Thread(
                    target=bhvr.run
                )
                ships_and_threads[ship_and_behaviour["name"]].start()
                time.sleep(10)  # stagger ships
                pass

            time.sleep(1)
