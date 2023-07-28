from procure_questWK2 import set_logging, sleep
import sys, json
from spacetraders_v2 import SpaceTraders
from spacetraders_v2.models import Waypoint, ShipyardShip, Market
from spacetraders_v2.contracts import Contract
import logging

logger = logging.getLogger(__name__)


def get_best_buy_price(st: SpaceTraders, trade_symbol):
    conn = st.db_client.connection


def master(st: SpaceTraders):
    ship = st.view_my_ships_one("CTRI-1")
    contracts = st.view_my_contracts()
    for contract in contracts.values():
        contract: Contract
        if not contract.fulfilled and contract.accepted:
            for deliverable in contract.deliverables:
                print(
                    f"{deliverable.symbol} {deliverable.units_required} / {deliverable.units_fulfilled} - reward = {contract.payment_completion}"
                )

    waypoints = st.find_waypoints_by_trait(ship.nav.system_symbol, "MARKETPLACE")
    waypoints.extend(st.find_waypoints_by_trait(ship.nav.system_symbol, "SHIPYARD"))
    sleep(ship.nav.travel_time_remaining)
    for waypoint in waypoints:
        waypoint: Waypoint
        resp = st.ship_move(ship, waypoint.symbol)

        sleep(ship.nav.travel_time_remaining + 1)
        st.ship_dock(ship)
        st.ship_refuel(ship)
        st.ship_orbit(ship)
        if not resp:
            logger.error(f"failed to move to {waypoint.symbol} because {resp.error}")

        if waypoint.has_market:
            logger.info("Found a market!")
            market = st.system_market(waypoint, True)

            continue
        if waypoint.has_shipyard:
            logger.info("Found a market!")
            shipyard = st.system_shipyard(waypoint.symbol, True)
            for ship_details in shipyard.ships:
                ship_details: ShipyardShip

            continue


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

    master(st)
