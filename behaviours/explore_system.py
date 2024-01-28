import sys

sys.path.append(".")
from behaviours.generic_behaviour import Behaviour
from straders_sdk import SpaceTraders
from straders_sdk.ship import Ship
from straders_sdk.models import Waypoint, System
import math
import logging
from straders_sdk.utils import try_execute_select, set_logging, waypoint_slicer
import networkx
import heapq
from datetime import datetime
import time

BEHAVIOUR_NAME = "EXPLORE_ONE_SYSTEM"
SAFETY_PADDING = 180


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
        self

    def run(self):
        super().run()
        self.sleep_until_ready()
        self.st.logging_client.log_beginning(
            BEHAVIOUR_NAME,
            self.ship.name,
            self.agent.credits,
            behaviour_params=self.behaviour_params,
        )
        self._run()
        self.end()

    def default_params_obj(self):
        return_obj = super().default_params_obj()
        return_obj["target_sys"] = "X1-BC28"

        return return_obj

    def _run(self):
        ship = self.ship
        st = self.st
        agent = st.view_my_self()
        # check all markets in the system
        self.o_sys = o_sys = st.systems_view_one(ship.nav.system_symbol)

        path = None
        if self.behaviour_params and "target_sys" in self.behaviour_params:
            d_sys = st.systems_view_one(self.behaviour_params["target_sys"])

            jg = st.find_waypoints_by_type_one(d_sys.symbol, "JUMP_GATE")
            st.waypoints_view_one(jg.symbol, True)
            st.system_jumpgate(jg, True)
            path = self.pathfinder.astar(o_sys, d_sys, force_recalc=True)
        else:
            d_sys = self.route_to_unexplored_jumpgate()
            if d_sys:
                d_sys = st.systems_view_one(d_sys)
                if not d_sys:
                    self.logger.error("Couldn't find system %s", d_sys)
                    self.end()
                    self.st.logging_client.log_ending(
                        BEHAVIOUR_NAME, ship.name, agent.credits
                    )
                    return
                path = self.pathfinder.astar(o_sys, d_sys, True)
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
                    self.st.sleep(600)
                    return
                target = resp[0]

                # target = try_execute_select(self.connection, tar_sys_sql, ())[0]
                d_sys = System(target[0], "", "", target[1], target[2], [])
                path = self.pathfinder.astar(o_sys, d_sys, bypass_check=True)
            self.logger.debug("Random destination selected: target %s", d_sys.symbol)

        arrived = True
        if ship.nav.system_symbol != d_sys.symbol:
            arrived = self.ship_extrasolar_jump(d_sys.symbol, path)
        if arrived:
            self.scan_local_system()
        else:
            self.logger.error("Couldn't jump! Unknown reason.")

        self.end()
        self.st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
        # travel to target system
        # scan target system

    def route_to_unexplored_jumpgate(self):
        source = self.st.find_waypoints_by_type(self.o_sys.symbol, "JUMP_GATE")
        if not source:
            self.st.sleep(SAFETY_PADDING)
            return None

        gate = self.st.system_jumpgate(source[0], True)
        for connected_system in gate.connected_waypoints:
            print(connection)


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "1"
    ship = f"{agent}-{ship_number}"
    behaviour_params = None
    # behaviour_params = {"priority": 3.5, "target_sys": "X1-DZ36"}  # X1-TF72 X1-YF83
    behaviour_params = {"priority": 3.5}
    bhvr = ExploreSystem(agent, ship, behaviour_params or {})

    lock_ship(ship, "MANUAL", duration=120)
    set_logging(logging.DEBUG)

    bhvr.run()
    lock_ship(ship, "", duration=0)
