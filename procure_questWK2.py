from spacetraders_v2.client_mediator import SpaceTradersMediatorClient as SpaceTraders
from spacetraders_v2.ship import Ship
from spacetraders_v2.models import Waypoint, Agent, ShipyardShip, Survey, Deposit
from spacetraders_v2.contracts import Contract
from spacetraders_v2.utils import sleep
import json
from spacetraders_v2.utils import set_logging
import logging
import sys
import math
import threading
from spacetraders_v2.utils import sleep

logger = logging.getLogger("game-file")


def mine_until_full(ship: Ship, st: SpaceTraders, survey: Survey = None):
    """mine until full, returns False if can't mine for any reason, True if ship is full"""
    current_location = st.waypoints_view_one(
        ship.nav.system_symbol, ship.nav.waypoint_symbol
    )
    current_location: Waypoint
    if current_location.type != "ASTEROID_FIELD":
        print("not at asteroid field, can't mine")
        return False

    while ship.cargo_units_used != ship.cargo_capacity:
        sleep(ship.seconds_until_cooldown + 1 + ship.nav.travel_time_remaining)

        resp = st.ship_extract(ship, survey)

        if not resp and resp.status_code != 409:
            # status code 409 means conflict, probably a cooldown, don't abort.
            return False
        if "extraction" in resp.data:
            ext_yield = resp.data["extraction"]["yield"]
            out_str = (
                f"{ship.name}, cargo {ship.cargo_units_used}/{ship.cargo_capacity}: extracted "
                + f"{ext_yield['symbol']}({ext_yield['units']})  survey used? "
                + f"{survey is not None}"
            )
            logger.info(out_str)
    return True


def wait_till_arrive(ship: Ship):
    if ship.nav.status == "IN_TRANSIT":
        print(f"ETA: {ship.nav.travel_time_remaining} - now sleeping")
        sleep(ship.nav.travel_time_remaining)
    return ship


def sell_all(ship: Ship, seller: Agent):
    sell_all_except(ship, seller, [])


def sell_all_except(ship: Ship, seller: Agent, exceptions: list):
    if ship.nav.status != "DOCKED":
        st.ship_dock(ship)
    starting_balance = seller.credits
    for cargo in ship.cargo_inventory:
        if cargo.symbol in exceptions:
            continue
        resp = st.ship_sell(ship, cargo.symbol, cargo.units)
        if not resp:
            logging.error("FAILED TO SELL CARGO %s", resp.error)
    logging.info(
        "%s sold all cargo for %s credits, new total: %s",
        ship.name,
        (seller.credits - starting_balance),
        seller.credits,
    )
    st.ship_orbit(ship)


def survey_until_hit(ship: Ship, material: str) -> Survey:
    "Survey until a given material is found"
    if not ship.can_survey:
        return None
    if ship.seconds_until_cooldown + ship.nav.travel_time_remaining > 0:
        sleep(max(ship.seconds_until_cooldown, ship.nav.travel_time_remaining))
    found = False
    sleep(max(ship.seconds_until_cooldown, ship.nav.travel_time_remaining))
    while len(st.find_surveys(material_symbol=material)) == 0:
        resp = ship.survey()
        if not resp:
            if resp.error_code == 4000:
                sleep(max(ship.seconds_until_cooldown, ship.nav.travel_time_remaining))
                continue
            continue

        sleep(max(ship.seconds_until_cooldown, ship.nav.travel_time_remaining))


def validate_and_fulfill(contract: Contract):
    for deliverable in contract.deliverables:
        if deliverable.units_fulfilled < deliverable.units_required:
            return False
    return st.contracts_fulfill(contract) is True


def extractor_quest_loop(
    ship: Ship, st: SpaceTraders, contract: Contract, viable_transports: list[Ship]
):
    target_material = contract.deliverables[0].symbol
    mining_site_wp = st.find_waypoint_by_type(ship.nav.system_symbol, "ASTEROID_FIELD")

    sleep(max(ship.seconds_until_cooldown, ship.nav.travel_time_remaining))
    if ship.nav.waypoint_symbol != mining_site_wp.symbol:
        st.ship_refuel(ship)
        st.ship_move(ship, mining_site_wp)
        if ship.can_survey:
            survey_until_hit(ship, target_material)

    while True:
        sleep(max(ship.seconds_until_cooldown, ship.nav.travel_time_remaining))
        best_survey = st.find_survey_best(target_material)

        for cargo in ship.cargo_inventory:
            if cargo.symbol == target_material:
                for target_ship in viable_transports:
                    space = target_ship.cargo_capacity - target_ship.cargo_units_used
                    if (
                        space == 0
                        or (target_ship.nav.travel_time_remaining > 0)
                        or (target_ship.nav.waypoint_symbol != ship.nav.waypoint_symbol)
                    ):
                        continue
                    if ship.nav.status != "IN_ORBIT":
                        st.ship_orbit(ship)
                    resp = st.ship_transfer_cargo(
                        ship, cargo.symbol, min(cargo.units, space), target_ship.name
                    )
                    if resp:
                        target_ship.receive_cargo(cargo.symbol, cargo.units)
                        st.update(target_ship)
                        # we could do this ourselves
                        logging.info(
                            "Transferring %s cargo to %s",
                            min(cargo.units, space),
                            target_ship.name,
                        )
                        break
                    else:
                        logging.error(
                            "Failed to transfer %s cargo to %s - %s",
                            min(cargo.units, space),
                            target_ship.name,
                            resp.error,
                        )

                # transfer cargo to first available transport

        if ship.cargo_capacity == ship.cargo_units_used:
            logging.info(
                f"ship full, selling all except {target_material}. ["
                + ", ".join([d.symbol for d in ship.cargo_inventory])
                + "]"
            )
            st.ship_dock(ship)
            # in the event that we try and transfer target but can't, we should keep it until the transport comes back
            sell_all_except(ship, st.current_agent, [target_material])

        if ship.can_extract and ship.cargo_capacity > ship.cargo_units_used:
            resp = st.ship_extract(ship, best_survey)
            if resp:
                logging.info(
                    f"Extracted {resp.data['extraction']['yield']['symbol']}({resp.data['extraction']['yield']['units']}), used surve? {best_survey is not None} "
                )
            else:
                sleep(ship.seconds_until_cooldown)
        else:
            # extractor that can't extract? shut it down.

            resp = st.ships_view_one(ship.name, True)
            if resp and isinstance(resp, Ship):
                ship = resp
            logging.error(f"Ship {ship.name} can't extract, pausing for 5 minutes.")
            sleep(300)


def surveyor_quest_loop(ship: Ship, st: SpaceTraders, contract: Contract):
    target_site_wp = contract.deliverables[0].destination_symbol
    target_material = contract.deliverables[0].symbol
    mining_site_wp = st.find_waypoint_by_type(ship.nav.system_symbol, "ASTEROID_FIELD")

    if ship.cargo_units_used >= ship.cargo_capacity - 10:
        st.ship_move(ship, target_site_wp)
    else:
        st.ship_move(ship, mining_site_wp)

    counter = 0
    sleep(max(ship.seconds_until_cooldown, ship.nav.travel_time_remaining))
    while True:
        sleep(max(ship.seconds_until_cooldown, ship.nav.travel_time_remaining))

        resp = st.ships_view_one(ship.name, True)
        if resp and isinstance(resp, Ship):
            ship = resp
        if ship.cargo_units_used >= ship.cargo_capacity - 10:
            logging.info("freighter full, returning to handin.")
            st.ship_orbit(ship)
            st.ship_move(ship, target_site_wp)
            sleep(ship.nav.travel_time_remaining)
            st.ship_dock(ship)
            st.ship_refuel(ship)
            for cargo in ship.cargo_inventory:
                if cargo.symbol == target_material:
                    st.contracts_deliver(contract, ship, target_material, cargo.units)

                    break
            logging.info(
                "contract delivered, %s of %s",
                contract.deliverables[0].units_fulfilled,
                contract.deliverables[0].units_required,
            )
            validate_and_fulfill(contract)
            st.ship_orbit(ship)
            st.ship_move(ship, mining_site_wp)
            sleep(ship.nav.travel_time_remaining)
            sell_all(ship, st.current_agent)
            sleep(max(ship.seconds_until_cooldown, ship.nav.travel_time_remaining))
        else:
            if ship.nav.status != "IN_ORBIT":
                st.ship_orbit(ship)
            if ship.nav.waypoint_symbol != mining_site_wp.symbol:
                logging.info(
                    "freighter in survey mode but not at mining site? moving to mining site."
                )
                st.ship_move(ship, mining_site_wp)
                sleep(ship.nav.travel_time_remaining)
        if ship.can_survey:
            if st.ship_survey(ship):
                best_survey = st.find_survey_best(target_material)
                if best_survey is not None:
                    hits = sum(
                        1 for d in best_survey.deposits if d.symbol == target_material
                    ) / len(best_survey.deposits)
                    logging.info(
                        "best survey to find %s is %s%% - ship cargo %s/%s",
                        target_material,
                        hits,
                        ship.cargo_units_used,
                        ship.cargo_capacity,
                    )

            else:
                sleep(70)
        else:
            sleep(30)


def master(st: SpaceTraders, contract: Contract):
    # start the drones
    st.view_my_self()
    ships = st.ships_view()
    extractors_and_threads = {}
    surveyors_and_threads = {}
    viable_transports = []
    target_extractors = 40
    target_surveyors = math.floor(target_extractors / 10)
    for ship in ships.values():
        if ship.role in ["HAULER", "COMMAND"]:
            thread = threading.Thread(
                target=surveyor_quest_loop, args=(ship, st, contract), name=ship.name
            )
            viable_transports.append(ship)
            surveyors_and_threads[ship.name] = thread
            thread.start()
            if len(surveyors_and_threads) >= target_surveyors:
                break
            sleep(20)

    for ship in ships.values():
        if ship.role in ["EXCAVATOR"]:
            thread = threading.Thread(
                target=extractor_quest_loop,
                args=(ship, st, contract, viable_transports),
                name=ship.name,
            )
            extractors_and_threads[ship.name] = thread

            thread.start()
            if len(extractors_and_threads) >= target_extractors:
                break
            sleep(5)

    # prepare buy loop
    shipyard_wp = st.find_waypoints_by_trait_one(
        list(ships.values())[0].nav.system_symbol, "SHIPYARD"
    )
    avail_ships = st.view_available_ships_details(shipyard_wp)
    if not avail_ships:
        logger.error(
            "failed to get available ships - will be unable to purchase new ships in this execution"
        )

    drone_cost = hauler_cost = 999999999
    if avail_ships and "SHIP_MINING_DRONE" in avail_ships:
        drone = avail_ships["SHIP_MINING_DRONE"]
        drone: ShipyardShip
        drone_cost = drone.purchase_price
    if avail_ships and "SHIP_LIGHT_HAULER" in avail_ships:
        hauler = avail_ships["SHIP_LIGHT_HAULER"]
        hauler: ShipyardShip
        hauler_cost = hauler.purchase_price

    agent = st.view_my_self(True)

    while (
        len(extractors_and_threads) < target_extractors
        or len(surveyors_and_threads) < target_surveyors
    ):
        if len(extractors_and_threads) < target_extractors:
            if agent.credits >= drone_cost * 2 or len(extractors_and_threads) < 2:
                new_ship = st.ship_purchase(shipyard_wp, "SHIP_MINING_DRONE")
                if not new_ship:
                    logger.error("failed to purchase new ship")
                thread = threading.Thread(
                    target=extractor_quest_loop,
                    args=(new_ship, st, contract, viable_transports),
                    name=new_ship.name,
                )

                extractors_and_threads[new_ship.name] = thread
                thread.start()

        if len(extractors_and_threads) / 10 > len(surveyors_and_threads):
            if agent.credits >= hauler_cost:
                new_ship = st.ship_purchase(shipyard_wp, "SHIP_LIGHT_HAULER")
                if not new_ship:
                    logger.error("failed to purchase new ship")
                thread = threading.Thread(
                    target=surveyor_quest_loop,
                    args=(new_ship, st, contract),
                    name=new_ship.name,
                )
                viable_transports.append(new_ship)
                surveyors_and_threads[new_ship.name] = thread
                thread.start()
        sleep(300)


if __name__ == "__main__":
    tar_username = sys.argv[1] if len(sys.argv) > 1 else None

    out_file = f"procure-quest.log"
    set_logging(out_file)

    with open("user.json", "r") as j_file:
        users = json.load(j_file)
    found_user = users["agents"][0]
    for user in users["agents"]:
        if user["username"] == tar_username:
            found_user = user
    st = SpaceTraders(
        found_user["token"],
        db_host=users["db_host"],
        db_name=users["db_name"],
        db_user=users["db_user"],
        db_pass=users["db_pass"],
        db_port=users["db_port"],
    )
    agent = st.view_my_self(True)
    st.logging_client.log_beginning("procure-quest (Week2)", agent.credits)
    contracts = list(
        c
        for c in st.view_my_contracts().values()
        if c.type == "PROCUREMENT" and not c.fulfilled
    )
    if len(contracts) == 0:
        # we have no job! Nothing to do.
        exit()
    contract = contracts[0]
    if not contract.accepted:
        st.contract_accept(contract.id)
    else:
        validate_and_fulfill(contract)
    print(
        f"contract remaining: {contract.deliverables[0].symbol}: {contract.deliverables[0].units_fulfilled} / {contract.deliverables[0].units_required}"
    )
    status = st.game_status()

    master(st, contract)
