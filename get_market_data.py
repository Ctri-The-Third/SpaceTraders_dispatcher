from procure_quest import set_logging, sleep
import sys, json
from spacetraders_v2 import SpaceTraders
from spacetraders_v2.models import Waypoint
import logging

logger = logging.getLogger(__name__)


def master():
    ship = st.view_my_ships_one("CTRI-1")

    threads = {}

    waypoints = st.find_waypoints_by_trait_one(ship.nav.system_symbol, "MARKETPLACE")
    for waypoint in waypoints:
        waypoint: Waypoint
        resp = st.ship_move(ship, waypoint.symbol)
        if not resp:
            logger.error(f"failed to move to {waypoint.symbol} because {resp.error}")
            sleep(5)
            continue
        sleep(ship.nav.travel_time_remaining)
        st.ship


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
    )

    master(st)
