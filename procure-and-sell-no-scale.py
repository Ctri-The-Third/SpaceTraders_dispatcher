import json
import sys
import threading
from spacetraders_v2.client_mediator import SpaceTradersMediatorClient as SpaceTraders
from spacetraders_v2.models import ShipyardShip
from spacetraders_v2.ship import Ship

from procure_questWK2 import (
    mine_until_full,
    wait_till_arrive,
    set_logging,
    sleep,
    logger,
    sell_all,
)


def master(st: SpaceTraders):
    # spin up the extractors and then termintae.

    # start the drones
    ships = st.view_my_ships()
    ships_and_threads = {}

    #    viable_transports = []
    #    for ship in ships.values():
    #        if ship.role in ["COMMAND"]:
    #            thread = threading.Thread(
    #                target=surveyor_quest_loop, args=(ship, st, contract), name=ship.name
    #            )
    #            viable_transports.append(ship)
    #            ships_and_threads[ship.name] = thread
    #            thread.start()
    #            sleep(10)

    for ship in ships.values():
        if ship.role in ["EXCAVATOR"]:
            thread = threading.Thread(
                target=extractor_quest_loop,
                args=(ship, st),
                name=ship.name,
            )
            ships_and_threads[ship.name] = thread
            thread.start()
            sleep(max(4, 60 / len(ships.values())))

    # prepare buy loop
    shipyard_wp = st.find_waypoints_by_trait_one(
        list(ships.values())[0].nav.system_symbol, "SHIPYARD"
    )
    avail_ships = st.view_available_ships_details(shipyard_wp)
    if not avail_ships:
        logger.error(
            "failed to get available ships - will be unable to purchase new ships in this execution"
        )

    cost = 999999999
    if avail_ships and "SHIP_MINING_DRONE" in avail_ships:
        drone = avail_ships["SHIP_MINING_DRONE"]
        drone: ShipyardShip
        cost = drone.purchase_price
    while len(st.ships) < 30:
        break  # no scaling
        agent = st.view_my_self(True)
        if agent.credits >= cost * 2 or len(st.ships) == 2:
            new_ship = st.ship_purchase(shipyard_wp, "SHIP_MINING_DRONE")
            if not new_ship:
                logger.error("failed to purchase new ship")
            thread = threading.Thread(
                target=extractor_quest_loop,
                args=(new_ship, st),
                name=new_ship.name,
            )

            ships_and_threads[new_ship.name] = thread
            thread.start()
        sleep(300)


def extractor_quest_loop(
    ship: Ship,
    st: SpaceTraders,
):
    mining_site_wp = st.find_waypoint_by_type(ship.nav.system_symbol, "ASTEROID_FIELD")

    sleep(max(ship.seconds_until_cooldown, ship.nav.travel_time_remaining))
    ship.orbit()
    if ship.nav.waypoint_symbol != mining_site_wp:
        ship.refuel()
        ship.move(mining_site_wp)

    while True:
        sleep(max(ship.seconds_until_cooldown, ship.nav.travel_time_remaining))
        best_survey = st.find_survey_best("PRECIOUS_STONES")

        if ship.can_extract:
            resp = ship.extract(best_survey)
            if bool(resp) is True:
                logger.info(
                    f"Extracted {resp.data['extraction']['yield']['symbol']}({resp.data['extraction']['yield']['units']}), used surve? {best_survey is not None} "
                )
            else:
                sleep(70)

        for cargo in ship.cargo_inventory:
            break
            if cargo.symbol == target_material:
                for target_ship in viable_transports:
                    space = target_ship.cargo_capacity - target_ship.cargo_units_used
                    if space == 0 or (
                        ship.nav.waypoint_symbol != target_ship.nav.waypoint_symbol
                    ):
                        continue
                    resp = ship.transfer_cargo(
                        cargo.symbol,
                        min(cargo.units, space),
                        target_ship.name,
                    )
                    if resp:
                        target_ship.force_update()
                        logging.info(
                            "Transferring %s cargo to %s",
                            min(cargo.units, space),
                            target_ship.name,
                        )
                        break
                # transfer cargo to first available transport

        if ship.cargo_capacity == ship.cargo_units_used:
            logger.info(
                f"ship full selling all. ["
                + ", ".join([d.symbol for d in ship.cargo_inventory])
                + "]"
            )
            ship.dock()
            # in the event that we try and transfer target but can't, we should keep it until the transport comes back
            sell_all(ship, st.current_agent)
            ship.orbit()


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
    st = SpaceTraders(found_user["token"])

    master(st)
