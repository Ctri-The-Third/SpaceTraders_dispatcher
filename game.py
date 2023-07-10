import time
import logging
import uuid
from spacetraders_v2.spacetraders import SpaceTraders
from spacetraders_v2.ship import Ship
from spacetraders_v2.models import Waypoint, WaypointTrait
from spacetraders_v2.models import Agent
import json
import re

ST = SpaceTraders()
ME: Agent = None


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
    st = ST
    try:
        user = json.load(open("user.json", "r"))
    except FileNotFoundError:
        register_and_store_user("creating_blank_file")
        exit()

    try:
        ST.token = user["agents"][0]["token"]
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
    print("--------")

    ships = st.view_available_ships(shipyards[0]).ships
    for ship in ships:
        print(f"{ship.type[5:]}\t{ship.purchase_price}\t{ship.description}")
    print("--------")

    # ship = st.purchase_ship(shipyards[0], "SHIP_MINING_DRONE")
    print(ship)


def menu():
    choice = 0
    announcements = ST.game_status().announcements
    ME = ST.view_my_self().agent
    for announcement in announcements:
        print(f"# {announcement.title}\n{announcement.body}\n")
    while choice != "x":
        print(
            """
1. View myself
2. View my contracts
3. View my ships
4. scan a system

x. Exit
           """
        )
        choice = input("Enter your choice: ")
        if choice == "1":
            display_me()
        elif choice == "2":
            display_contracts()
        elif choice == "3":
            display_ships()
        elif choice == "4":
            scan_system()


def display_ships():
    resp = ST.view_my_ships()

    if not resp:
        print(resp.error)
        return
    print("** ALL SHIPS **")
    counter = 0
    for ship in resp.ships:
        # I want to print a counter:
        time = ship.nav.time_remaining()

        eta = f" ETA: {ship.nav.time_remaining()}" if time.total_seconds() > 0 else ""
        print(f"{counter}: {ship.name}\t{ship.role} - \t{ship.nav.waypoint_symbol}")
        counter += 1

    ship_id = input(
        "enter list number to view ship commands, or just enter to continue: "
    )
    try:
        ship = resp.ships[int(ship_id)]
        ship_menu(ship)
    except (IndexError, ValueError):
        print("ship selection not recognised")


def _time_to_destination(ship: Ship):
    """returns the time to destination in mm:ss"""
    if ship.nav == None:
        return 0
    else:
        return ship.destination.time_remaining


def ship_menu(ship: Ship):
    choice = 0

    print(f" COMMANDING: {ship.name} \n")
    print("------------------------")
    print("SYSTEM RESULTS:")
    _scan_system(ship.nav.system_symbol)
    print("------------------------\n")

    print("O: Undock/ Orbit")
    print("M: Move")
    print("E: Extract (mine)")
    print("W: Warp")
    choice = input("enter command or press enter to continue: ").upper()

    if choice == "O":
        resp = ST.ship_orbit(ship.name)

    elif choice == "M":
        move_ship(ship, input("enter destination or co-ords: "))

    elif choice == "E":
        print(f"{ship.cargo_units_used}/{ship.cargo_capacity}")
        resp = ST.ship_extract(ship.name)
        while resp and len(resp.extraction) > 0:
            if not resp:
                print(resp.error)
                return
            print(resp.cooldown)
            print(resp.extraction)

            time.sleep(72)
            resp = ST.ship_extract(ship.name)

    elif choice == "W":
        pass
    else:
        return
    if not resp:
        print(resp.error)
        return


def move_ship(ship: Ship, dest_str):
    """moves ship between waypoints in a system."""
    waypoint_match = re.match("^[A-Z0-9]{2,4}-[A-Z0-9]{2,4}-[A-Z0-9]{6}$", dest_str)
    coordinates_match = re.match(r"(-?\d+),?(-?\d+)", dest_str)

    if waypoint_match:
        waypoint_symbol = waypoint_match.group(1)
    elif coordinates_match:
        x = int(coordinates_match.group(1))
        y = int(coordinates_match.group(2))

        waypoint_symbol = ST.find_waypoint_by_coords(ship.current_system, x, y) or ""
    if not waypoint_symbol:
        print("destination not recognised")
        return
    resp = ST.ship_move(ship.name, waypoint_symbol)
    if not resp:
        print(resp.error)
        return
    ship.fuel_current = resp.fuel_current
    ship.fuel_capacity = resp.fuel_capacity

    print(f"Ship {ship.name} is moving to somewhere else")


def scan_system():
    system_symbol = input("Enter system: ").upper()
    _scan_system(system_symbol)
    input("press enter to continue")


def _scan_system(waypoint_symbol: str) -> list[Waypoint]:
    resp = ST.view_waypoints(waypoint_symbol)
    if not resp:
        print(resp.error)
        return
    print("** ALL WAYPOINTS **")
    for waypoint in resp.waypoints:
        out_str = f"{waypoint.symbol}\t{waypoint.type} [{waypoint.x},{waypoint.y}]\t- "
        out_str += ", ".join([trait.symbol for trait in waypoint.traits])
        print(out_str)


def display_me():
    me = ST.view_my_self()
    if not me:
        print(me.error)
        return
    print(
        f"""
** CURRENT AGENT **                  
Username: \t {me.agent.symbol}
Credits: \t {me.agent.credits}
"""
    )


if __name__ == "__main__":
    # subprocess.call(["setup.bat"], shell=True)
    main()
    menu()
