import sys

sys.path.append(".")
from behaviours.generic_behaviour import Behaviour
from straders_sdk import SpaceTraders
from straders_sdk.ship import Ship
from straders_sdk.models import Waypoint, System
import math
import logging
from straders_sdk.utils import try_execute_select, set_logging
import networkx
import heapq
from datetime import datetime
import time

BEHAVIOUR_NAME = "EXPLORE_ONE_SYSTEM"


class ExploreSystem(Behaviour):
    """This behaviour will explore a single system, scanning all the markets and then returning to the original system.

    Expects behaviour_params with the following keys:
    - `target_sys`: the system to explore
    """

    def __init__(
        self,
        agent_name,
        ship_name,
        behaviour_params: dict = ...,
        config_file_name="user.json",
    ) -> None:
        self.graph = None
        super().__init__(agent_name, ship_name, behaviour_params, config_file_name)

    def run(self):
        super().run()
        ship = self.ship
        st = self.st
        agent = st.view_my_self()
        # check all markets in the system
        st.logging_client.log_beginning(BEHAVIOUR_NAME, ship.name, agent.credits)

        self.sleep_until_ready()

        if self.behaviour_params and "target_sys" in self.behaviour_params:
            d_sys = st.systems_view_one(self.behaviour_params["target_sys"])
        else:
            tar_sys_sql = """SELECT w1.system_symbol, j.x, j.y, last_updated, jump_gate_waypoint
                    FROM public.mkt_shpyrds_systems_last_updated_jumpgates j
                    JOIN waypoints w1 on j.waypoint_symbol = w1.waypoint_symbol
                    order by last_updated, random()"""
            resp = try_execute_select(self.connection, tar_sys_sql, ())

            if not resp:
                self.logger.error(
                    "Couldn't find any systems with jump gates! sleeping  10 mins then exiting!"
                )
                time.sleep(600)
                return
            target = resp[0]
            # target = try_execute_select(self.connection, tar_sys_sql, ())[0]
            self.logger.debug("Random destination selected: target %s", target[0])
            d_sys = System(target[0], "", "", target[1], target[2], [])

        arrived = True
        if ship.nav.system_symbol != d_sys.symbol:
            arrived = self.ship_extrasolar(d_sys)
        if not arrived:
            self.logger.error("Couldn't jump! Unknown reason.")
            return
        self.scan_local_system()
        # travel to target system
        # scan target system


if __name__ == "__main__":
    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "ZTRI-0-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "2"
    ship = f"{agent}-{ship_number}"
    behaviour_params = None
    # behaviour_params = {"target_sys": "X1-JX88"}
    bhvr = ExploreSystem(agent, ship, behaviour_params or {})

    bhvr.run()
