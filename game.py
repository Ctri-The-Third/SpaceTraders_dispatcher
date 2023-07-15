import time
import logging
from sys import stdout
from logging import FileHandler, StreamHandler
import uuid
from spacetraders_v2.client_mediator import SpaceTradersMediatorClient as SpaceTraders
from spacetraders_v2.ship import Ship
from spacetraders_v2.contracts import Contract
from spacetraders_v2.models import (
    Waypoint,
    WaypointTrait,
    Agent,
    ShipyardShip,
    ShipModule,
    ShipMount,
)

import json
import re

ST = SpaceTraders()
ME: Agent = None

format = "%(asctime)s:%(levelname)s:%(name)s  %(message)s"
logging.basicConfig(
    handlers=[FileHandler("presence.log"), StreamHandler(stdout)],
    level=logging.DEBUG,
    format=format,
)
logging.getLogger("urllib3").setLevel(logging.WARNING)


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

    # status = st.game_status()
    # registration = st.register(uuid.uuid4().hex[:14])

    # self = st.view_my_self()
    ships: dict[str:Ship] = st.view_my_ships()
    ship: Ship = list(ships.values())[1]

    waypoints = st.waypoints_view(ship.nav.system_symbol)
    shipyards = [
        waypoint
        for waypoint in waypoints.values()
        for trait in waypoint.traits
        if trait.symbol == "SHIPYARD"
    ]
    ships_avail = st.view_available_ships_details(shipyards[0])
    for ship in ships_avail.values():
        ship: ShipyardShip
        print(ship)
        print(f"------ {ship.type} -----")
        print(f"{ship.name}: {ship.description} ")
        print(f"cost: {ship.purchase_price}")
        print("-- modules")
        for module in ship.modules:
            print(f"* {module.name}: {module.description}")
        print("-- mounts")
        for mount in ship.mounts:
            print(f"* {mount.name}: {mount.description}")
    # resp = st.ship_purchase(shipyards[0], "SHIP_MINING_DRONE")
    # new_ship = Ship(resp.data["ship"], st)

    # resp = ship.orbit()

    # ship = st.purchase_ship(shipyards[0], "SHIP_MINING_DRONE")


def menu():
    choice = 0
    announcements = ST.game_status().announcements
    ME = ST.view_my_self()
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


def display_contracts():
    contracts = ST.view_my_contracts()


def display_ships():
    ships = ST.view_my_ships()

    if not ships:
        print(ships.error)
        return
    print("** ALL SHIPS **")
    counter = 0
    for _, ship in ships.items():
        # I want to print a counter:
        time = ship.nav.travel_time_remaining()
        eta = ""
        if ship.nav.status == "IN_TRANSIT":
            mins = time // 60
            secs = time % 60
            eta = f" ETA: {mins}:{secs}"
        print(
            f"{counter}: {ship.name}\t{ship.role} - \t{ship.nav.waypoint_symbol} {ship.nav.status}"
        )
        counter += 1

    ship_id = input(
        "enter list number to view ship commands, or just enter to continue: "
    )
    if ship_id == "":
        return
    try:
        ship = list(ships.values())[int(ship_id)]
        ship_menu(ship)

    except (IndexError, ValueError):
        print("ship selection not recognised")


def ship_menu(ship: Ship):
    choice = 0
    while choice not in ["x", ""]:
        print(f" COMMANDING: {ship.name} \n")
        print(
            f"LOC: {ship.nav.waypoint_symbol}   {ship.nav.origin.type}   {ship.nav.status}"
        )
        if ship.nav.status == "IN_TRANSIT":
            print(
                f"NAV: {ship.nav.travel_time_remaining}   {ship.nav.destination.type}   {ship.nav.destination.symbol}"
            )
        print("------------------------")
        print("SYSTEM RESULTS:")
        _scan_system(ship.nav.system_symbol)
        print("------------------------\n")

        choice = input("enter command or press enter to continue: ").upper()
        if choice == "H":
            print("O: Undock/ Orbit")
            print("M: Move")
            print("E: Extract (mine)")
            print("D: Dock")
            print("R: Refuel & Repair")
            print("S: Sell all Cargo")
            print("W: Warp")
        if choice == "O":
            resp = ship.orbit()

        elif choice == "M":
            resp = move_ship(ship, input("enter destination or co-ords: "))

        elif choice == "E":
            print(f"{ship.cargo_units_used}/{ship.cargo_capacity}")
            resp = ship.extract()
            while resp and len(resp.extraction) > 0:
                if not resp:
                    print(resp.error)
                    return
                print(resp.cooldown)
                print(resp.extraction)

                time.sleep(72)
                resp = ship.extract()
        elif choice == "W":
            pass
        elif choice == "D":
            resp = ship.dock()
        elif choice == "S":
            resp = ship.sell_all()

        else:
            return
        if resp is not None and not resp:
            print(resp.error)
            print("returning to main menu")
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

        waypoint_symbol = ST.find_waypoint_by_coords(ship.nav.system_symbol, x, y) or ""
    if not waypoint_symbol:
        print("destination not recognised")
        return None
    resp = ship.move(waypoint_symbol)
    if not resp:
        print(resp.error)
        return None
    return resp

    print(f"Ship {ship.name} is moving to somewhere else")


def scan_system():
    system_symbol = input("Enter system: ").upper()
    _scan_system(system_symbol)
    input("press enter to continue")


def _scan_system(system_symbol: str) -> list[Waypoint]:
    waypoints = ST.waypoints_view(system_symbol)
    if not waypoints:
        print(waypoints.error)
        return
    print("** ALL WAYPOINTS **")
    for symbol, waypoint in waypoints.items():
        waypoint: Waypoint
        out_str = f"{symbol}\t{waypoint.type} [{waypoint.x},{waypoint.y}]\t- "
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
Username: \t {me.symbol}
Credits: \t {me.credits}
"""
    )


if __name__ == "__main__":
    # subprocess.call(["setup.bat"], shell=True)
    register_and_store_user("CTRI")
    # menu()
    main()
    contracts = ST.view_my_contracts()
    if not contracts:
        print(contracts.error)
        exit()

    for contract in contracts.values():
        contract: Contract
        print(
            f"{contract.id[0:4]} - accepted:{contract.accepted}, fulfilled:{contract.fulfilled}"
        )
    print(contracts)
    # menu()
