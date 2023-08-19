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

        time.sleep(max(ship.seconds_until_cooldown, ship.nav.travel_time_remaining))

        if self.behaviour_params and "target_sys" in self.behaviour_params:
            d_sys = st.systems_view_one(self.behaviour_params["target_sys"])
        else:
            tar_sys_sql = """SELECT w1.system_symbol, j.x, j.y, last_updated, jump_gate_waypoint
                    FROM public.mkt_shpyrds_systems_last_updated_jumpgates j
                    JOIN waypoints w1 on j.symbol = w1.symbol
                    order by last_updated, random()"""
            target = try_execute_select(self.connection, tar_sys_sql, ())[0]
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
    agent_symbol = "CTRI-RWK5-"
    ship_suffix = "1"
    params = None
    systems = [
        "X1-B55",
        "X1-HK30",
        "X1-PC83",
        "X1-MC83",
        "X1-RK61",
        "X1-UC71",
        "X1-GU26",
        "X1-YD18",
        "X1-AS94",
        "X1-HY95",
        "X1-AT36",
        "X1-J81",
        "X1-GH56",
        "X1-HK27",
        "X1-YF6",
        "X1-NJ19",
        "X1-YS39",
        "X1-BH54",
        "X1-Z79",
        "X1-MQ25",
    ]
    for system in systems:
        logging.info(f"==STARTING EXPLORE OF {system}==")
        params = {"asteroid_wp": "", "target_sys": system}
        ExploreSystem(agent_symbol, f"{agent_symbol}-{ship_suffix}", params).run()
