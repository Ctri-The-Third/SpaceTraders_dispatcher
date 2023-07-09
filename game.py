import subprocess
import logging
import uuid
from spacetraders_v2.spacetraders import SpaceTraders
import sys
import json


def register_and_store_user(username):
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


def main():
    # Create a SpaceTraders instance
    user = json.load(open("user.json", "r"))

    st = SpaceTraders(user["agents"][0]["token"])

    # Get the game status
    status = st.game_status()
    if not status:
        return

    contracts = st.view_my_contracts().contracts
    #    st.accept_contract("cljvdhlwy3j29s60cu9upccp1")
    agent = st.view_my_self().agent
    st.view_waypoints(agent.headquaters)
    print(contracts)


if __name__ == "__main__":
    # subprocess.call(["setup.bat"], shell=True)
    main()
