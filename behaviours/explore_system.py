import sys

sys.path.append(".")
from behaviours.generic_behaviour import Behaviour
from straders_sdk import SpaceTraders
from straders_sdk.ship import Ship
from straders_sdk.models import Waypoint, System
from straders_sdk.pathfinder import JumpGateRoute
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
            path, next_step = self.route_to_uncharted_jumpgate()
            path: JumpGateRoute
            if path:
                d_sys = path.end_system
            else:
                d_sys = o_sys
            self.logger.debug("Random destination selected: target %s", d_sys.symbol)

        arrived = True
        if d_sys.symbol != o_sys.symbol:
            if ship.nav.system_symbol != d_sys.symbol:
                arrived = self.ship_extrasolar_jump(d_sys.symbol, path)
            else:
                local_gates = st.find_waypoints_by_type(d_sys.symbol, "JUMP_GATE")
                if local_gates:
                    self.ship_intrasolar(local_gates[0].symbol)
                    arrived = self.st.ship_jump(ship, next_step)

        if arrived:
            self.scan_local_system()
        else:
            self.logger.error("Couldn't jump! Unknown reason.")

        self.end()
        self.st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
        # travel to target system
        # scan target system

    def route_to_uncharted_jumpgate(
        self,
    ) -> tuple["JumpRoute", Waypoint]:
        source = self.st.find_waypoints_by_type(self.o_sys.symbol, "JUMP_GATE")
        if not source:
            self.st.sleep(SAFETY_PADDING)
            return None

            pass

        source = self.st.waypoints_view_one(source[0].symbol, True)
        if not source.is_charted:
            return (None, source)
        gate = self.st.system_jumpgate(source)
        for connected_waypoint in gate.connected_waypoints:
            wayp = self.st.waypoints_view_one(connected_waypoint)
            if (
                "UNCHARTED" in [t.symbol for t in wayp.traits] and not wayp.is_charted
            ) and not wayp.under_construction:
                route = self.pathfinder.astar(
                    self.o_sys, self.st.systems_view_one(wayp.system_symbol)
                )
                if route:
                    return (route, connected_waypoint)
            print(connected_waypoint)
        return (None, None)


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "1"
    ship = f"{agent}-{ship_number}"
    behaviour_params = None
    behaviour_params = {"priority": 3.5, "target_sys": "X1-ZV83"}  # X1-TF72 X1-YF83
    # behaviour_params = {"priority": 3.5}
    bhvr = ExploreSystem(agent, ship, behaviour_params or {})

    lock_ship(ship, "MANUAL", duration=120)
    set_logging(logging.DEBUG)

    bhvr.run()
    lock_ship(ship, "", duration=0)
