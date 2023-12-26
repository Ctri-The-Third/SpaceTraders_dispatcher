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
from straders_sdk import SpaceTraders
import random

BEHAVIOUR_NAME = "WARP_TO_SYSTEM"
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

        route = self.pathfinder.plot_warp_nav(start_sys, end_sys, ship.fuel_capacity)

        distance = self.pathfinder.calc_distance_between(start_sys, end_sys)
        if distance > ship.fuel_capacity:
            total_fuel_needed = (distance - ship.fuel_current) / 100
            self.top_up_the_tank()
        if not route:
            self.logger.warning("No route found, exiting")
            time.sleep(SAFETY_PADDING)
            return
        route.route.pop(0)
        last_sys = start_sys
        for node in route.route:
            sys = st.systems_view_one(node)
            wayps = st.find_waypoints_by_type(sys.symbol, "ORBITAL_STATION")
            if not wayps:
                wayps = st.find_waypoints_by_type(sys.symbol, "PLANET")
            if not wayps:
                wayps = st.find_waypoints_by_type(sys.symbol, "GAS_GIANT")
            if not wayps:
                wayps = list(st.waypoints_view(sys.symbol).values())

            self.sleep_until_arrived()
            st.ship_scan_waypoints(ship)
            distance = self.pathfinder.calc_distance_between(last_sys, sys)
            if distance > ship.fuel_current:
                resp = st.ship_patch_nav(ship, "DRIFT")
            else:
                resp = st.ship_patch_nav(ship, "CRUISE")
            resp = st.ship_warp(ship, wayps[0].symbol)
            if not resp:
                break

            last_sys = sys

    def top_up_the_tank(self, found_wayps: list = None):
        wayps = found_wayps or []
        wayps = [w for w in wayps if w.has_market]
        if not wayps:
            wayps = self.st.find_waypoints_by_trait(
                self.ship.nav.system_symbol, "MARKETPLACE"
            )
        if not wayps:
            self.scan_local_system()
            wayps = self.st.find_waypoints_by_trait(
                self.ship.nav.system_symbol, "MARKETPLACE"
            )
        if not wayps:
            return
        self.ship_intrasolar(wayps[0].symbol)
        self.go_and_buy("FUEL", wayps[0], max_to_buy=self.ship.fuel_capacity)
        self.st.ship_refuel(self.ship)


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
