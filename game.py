import subprocess
import logging
import uuid
from spacetraders_v2.spacetraders import SpaceTraders
from spacetraders_v2.models import Waypoint, WaypointTrait
import sys
import json


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
        if resp.token == agent["token"]:
            found = True
    if not found:
        user["agents"].append({"token": resp.token, "username": username})
    json.dump(user, open("user.json", "w"), indent=2)
    return resp.token


def main():
    # Create a SpaceTraders instance
    try:
        user = json.load(open("user.json", "r"))
    except FileNotFoundError:
        register_and_store_user("creating_blank_file")
        exit()

    try:
        st = SpaceTraders(user["agents"][0]["token"])
    except IndexError:
        register_and_store_user(uuid.uuid4().hex[:14])
        exit()

    # Get the game status
    status = st.game_status()
    if not status:
        return

    contracts = st.view_my_contracts().contracts
    st.accept_contract(contracts[0].id)
    agent = st.view_my_self().agent
    waypoints = st.view_waypoints(agent.headquaters[0:6]).waypoints
    # shipyards = []
    # for waypoint in waypoints:  #
    #    waypoint: Waypoint
    #    print(f"{waypoint} -- {waypoint.type}")
    #    for trait in waypoint.traits:
    #        if trait.symbol == "SHIPYARD":
    shipyards = [
        waypoint
        for waypoint in waypoints
        for trait in waypoint.traits
        if trait.symbol == "SHIPYARD"
    ]
    print(shipyards)

    st.view_available_ships(shipyards[0])
    print("--------")


if __name__ == "__main__":
    # subprocess.call(["setup.bat"], shell=True)
    main()
