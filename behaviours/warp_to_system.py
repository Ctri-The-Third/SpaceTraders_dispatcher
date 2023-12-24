# takes a tradegood. Then trades that to ensure that the market is LIMITED
# if the export activity hits RESTRICTED, it switches to finding profitable import goods until that clears.

# script is happy to work to 0 profit, but will not work at a loss.


import time
import sys


sys.path.append(".")
from behaviours.generic_behaviour import Behaviour
import logging
from straders_sdk.ship import Ship
from straders_sdk.models import Market, Waypoint
from straders_sdk.utils import waypoint_slicer, set_logging, try_execute_select
from straders_sdk.constants import SUPPLY_LEVELS
from behaviours.generic_behaviour import Behaviour
import random

BEHAVIOUR_NAME = "NEW_BEHAVIOUR"
SAFETY_PADDING = 180


class WarpToSystem(Behaviour):
    def __init__(
        self,
        agent_name,
        ship_name,
        behaviour_params: dict = ...,
        config_file_name="user.json",
        session=None,
        connection=None,
    ) -> None:
        super().__init__(
            agent_name,
            ship_name,
            behaviour_params,
            config_file_name,
            session,
            connection,
        )
        self.agent = self.st.view_my_self()
        self.logger = logging.getLogger(BEHAVIOUR_NAME)
        self.destination_sys = self.behaviour_params.get("target_sys", None)

    def run(self):
        self.ship = self.st.ships_view_one(self.ship_name)
        self.sleep_until_ready()
        self.st.logging_client.log_beginning(
            BEHAVIOUR_NAME,
            self.ship.name,
            self.agent.credits,
            behaviour_params=self.behaviour_params,
        )
        self._run()
        self.end()

    def _run(self):
        st = self.st
        ship = self.ship  # = st.ships_view_one(self.ship_name, True)
        ship: Ship
        agent = self.agent

        if not ship.can_warp:
            self.logger.warning("Ship cannot warp, exiting")
            time.sleep(SAFETY_PADDING)
            return
        start_sys = st.systems_view_one(ship.nav.system_symbol)
        end_sys = st.systems_view_one(self.destination_sys)

        route = self.pathfinder.plot_warp_nav(
            start_sys, end_sys, ship.fuel_capacity, True
        )

        distance = route.total_distance

        if not route:
            self.logger.warning("No route found, exiting")
            time.sleep(SAFETY_PADDING)
            return

        for node in route.route:
            st.ship_warp(ship, node.jump_gate_waypoint)


#
# to execute from commandline, run the script with the agent and ship_symbol as arguments, or edit the values below
#
if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "58"
    ship = f"{agent}-{ship_number}"
    behaviour_params = {"priority": 3, "target_sys": "X1-SR25"}

    bhvr = WarpToSystem(agent, ship, behaviour_params or {})

    lock_ship(ship, "MANUAL", bhvr.st.db_client.connection, 60 * 24)

    bhvr.run()
    lock_ship(ship, "MANUAL", bhvr.st.db_client.connection, 0)
