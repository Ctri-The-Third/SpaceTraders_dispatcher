# this is the ship dispatcher / conductor script.
# It will get unlocked ships from the DB, check their behaviour ID and if it matches a known behaviour, lock the ship and execute the behaviour.
import json
import logging
import psycopg2
from spacetraders_v2 import SpaceTraders

from behaviours.extract_and_sell import ExtractAndSell


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


if __name__ == "__main__":
    register_and_store_user("O2O")

    user = json.load(open("user.json", "r"))
    st = SpaceTraders(
        user["agents"][1]["token"],
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
    fallback_blob = {
        "token": st.token,
        "hq_sys": hq_sys,
        "hq_wayp": list(ships.values())[1].nav.waypoint_symbol,
        "market_wayp": st.find_waypoints_by_trait_one(hq_sys, "MARKETPLACE").symbol,
        "shipyard_wayp": st.find_waypoints_by_trait_one(hq_sys, "SHIPYARD").symbol,
    }
    print(json.dumps(fallback_blob, indent=2))

    # get unlocked ships
    connection = psycopg2.connect(
        host=user["db_host"],
        port=user["db_port"],
        database=user["db_name"],
        user=user["db_user"],
        password=user["db_pass"],
    )
    connection.autocommit = True
    behaviours = {
        "EXTRACT_AND_SELL": ExtractAndSell,
    }
    ships_and_threads = {}
    # need to assign default behaviours here.

    # get unlocked ships with behaviours
    unlocked_ships = [{"name": "ship_id", "behaviour_id": "EXTRACT_AND_SELL"}]
    for ship_and_behaviour in unlocked_ships.values():
        # do we have a
        behaviour_type = behaviours.get(ship.behaviour_id, None)
        behaviour_type: type
        if not behaviour_type:
            continue
        #we know this is behaviour, so pass it the values and execute it in its own thread.
        behaviour_type()
        ships_and_threads[ship_symbol] = threading.Thread(