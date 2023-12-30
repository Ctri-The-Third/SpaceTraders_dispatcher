# takes a tradegood. Then trades that to ensure that the market is LIMITED
# if the export activity hits RESTRICTED, it switches to finding profitable import goods until that clears.

# script is happy to work to 0 profit, but will not work at a loss.


import time
import sys


sys.path.append(".")
from behaviours.generic_behaviour import Behaviour
import logging
from straders_sdk.ship import Ship
from straders_sdk.models import Market, Waypoint, System
from straders_sdk.utils import waypoint_slicer, set_logging, try_execute_select
from straders_sdk.constants import SUPPLY_LEVELS
from behaviours.generic_behaviour import Behaviour
from straders_sdk import SpaceTraders
from straders_sdk.pathfinder.route import JumpGateSystem
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
        current_sys = st.systems_view_one(ship.nav.system_symbol)
        dest_sys = st.systems_view_one(self.destination_sys)

        while ship.nav.system_symbol != dest_sys.symbol:
            print(
                f"current system: {current_sys.symbol}, dest: {dest_sys.symbol} - distance {self.pathfinder.calc_distance_between(current_sys, dest_sys)}"
            )
            jump_route = self.pathfinder.astar(current_sys, dest_sys, True, False)

            if jump_route:
                self.ship_extrasolar_jump(jump_route.route[1].symbol)
                current_sys = st.systems_view_one(ship.nav.system_symbol)
                next_sys = self.find_jumpgate_on_way_to(
                    dest_sys,
                    max_range=3500,
                    origin_x=current_sys.x,
                    origin_y=current_sys.y,
                )
                if next_sys:
                    self.ship_extrasolar_warp(next_sys.symbol)

            if not jump_route:
                self.logger.warning("No jump route found - warping the whole way")
                self.ship_extrasolar_warp(dest_sys.symbol)

    def ship_extrasolar_warp(self, dest_sys: str, ship: Ship = None):
        st = self.st
        ship = ship or self.ship
        if not ship.can_warp:
            return False
        if ship.nav.system_symbol == dest_sys:
            return True
        start_sys = st.systems_view_one(ship.nav.system_symbol)
        dest_sys = st.systems_view_one(dest_sys)
        route = self.pathfinder.plot_warp_nav(start_sys, dest_sys, ship.fuel_capacity)

        distance = self.pathfinder.calc_distance_between(start_sys, dest_sys)
        if distance > ship.fuel_capacity:
            total_fuel_needed = (distance - ship.fuel_current) / 100
            self.top_up_the_tank()
        if not route:
            self.logger.warning("No route found, exiting")
            time.sleep(SAFETY_PADDING)
            return
        route.route.pop(0)  # remove the first system, as we're already there.
        last_sys = start_sys
        distance_remaining = route.total_distance
        fuel_in_tank = (
            sum([c.units for c in ship.cargo_inventory if c.symbol == "FUEL"]) * 100
        )
        for node in route.route:
            self.sleep_until_arrived()
            ship.nav.status = "IN_ORBIT"
            st.ship_scan_waypoints(ship)

            sys = st.systems_view_one(node)
            wayps = st.find_waypoints_by_type(sys.symbol, "ORBITAL_STATION")
            if not wayps:
                wayps = st.find_waypoints_by_type(sys.symbol, "JUMP_GATE")
            if not wayps:
                wayps = st.find_waypoints_by_type(sys.symbol, "PLANET")
            if not wayps:
                wayps = st.find_waypoints_by_type(sys.symbol, "GAS_GIANT")
            if not wayps:
                wayps = list(st.waypoints_view(sys.symbol).values())

            distance = self.pathfinder.calc_distance_between(last_sys, sys)
            # print(
            #    f"distance: {round(distance,2)}, fuel: {ship.fuel_current} - projected fuel: { ship.fuel_current - distance}"
            # )
            if distance_remaining > ship.fuel_current + fuel_in_tank:
                self.top_up_the_tank(wayps)
                fuel_in_tank = (
                    sum([c.units for c in ship.cargo_inventory if c.symbol == "FUEL"])
                    * 100
                )
            if distance >= ship.fuel_current and distance < ship.fuel_capacity:
                st.ship_refuel(ship, True)
                fuel_in_tank = (
                    sum([c.units for c in ship.cargo_inventory if c.symbol == "FUEL"])
                    * 100
                )
            # if there's a market in the system - we need to go there and top up the tank.
            if distance > ship.fuel_current and ship.nav.flight_mode != "DRIFT":
                resp = st.ship_patch_nav(ship, "DRIFT")
            elif distance <= ship.fuel_current and ship.nav.flight_mode != "CRUISE":
                resp = st.ship_patch_nav(ship, "CRUISE")

            if ship.nav.status != "IN_ORBIT":
                st.ship_orbit(ship)
            resp = st.ship_warp(ship, wayps[0].symbol)
            distance_remaining -= distance
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

    def find_jumpgate_on_way_to(
        self, dest_system: "System", max_range: int, origin_x=None, origin_y=None
    ):
        if not origin_x or not origin_y:
            origin_s = self.st.systems_view_one(self.ship.nav.system_symbol)
            origin_x = origin_s.x
            origin_y = origin_s.y
        dest_x = dest_system.x
        dest_y = dest_system.y
        sql = """
        
        select w.waypoint_symbol, s.system_symbol, s.x, s.y from systems s 
        join waypoints w on s.system_symbol = w.system_symbol
        where (s.x between  %s  and %s) and s.y between %s and %s
        and w.type = 'JUMP_GATE'
        """
        gates = try_execute_select(
            self.connection,
            sql,
            (
                min(origin_x, dest_x),
                max(origin_x, dest_x),
                min(origin_y, dest_y),
                max(origin_y, dest_y),
            ),
        )

        gates = [JumpGateSystem(g[1], "", "", g[2], g[3], [], g[0]) for g in gates]
        # find the one whose total total distance is inside max_range and closest to the destination, and return it.
        # this assumes we'll probably warp this distance faster than the cooldown to reusing the jump gate.
        best_gate = None
        best_gate_distance = float("inf")
        for gate in gates:
            route = self.pathfinder.astar(gate, dest_system, True, False)
            if route.total_distance < best_gate_distance:
                best_gate = gate
                best_gate_distance = route.total_distance

        return best_gate

    def find_nearest_jumpgate(self, system: "System", max_range: int = 3500):
        sql = """
        select w.waypoint_symbol, s.system_symbol, s.x, s.y from systems s
        join waypoints w on s.system_symbol = w.system_symbol
        where w.type = 'JUMP_GATE'
        and s.x between %s and %s
        and s.y between %s and %s
        """
        gates = try_execute_select(
            self.connection,
            sql,
            (
                system.x - max_range,
                system.x + max_range,
                system.y - max_range,
                system.y + max_range,
            ),
        )

        gates = [JumpGateSystem(g[1], "", "", g[2], g[3], [], g[0]) for g in gates]
        # find the one whose total total distance is inside max_range and closest to the destination, and return it.

        best_gate = None
        best_gate_distance = float("inf")
        for gate in gates:
            print(f"ABOUT TO DO {gate.symbol}")
            route = self.pathfinder.astar(gate, system, True, False)
            if route:
                if route.total_distance == 0:
                    best_gate = gate
                    return best_gate
                if route.total_distance < best_gate_distance:
                    best_gate = gate
                    best_gate_distance = route.total_distance
        return best_gate


#
# to execute from commandline, run the script with the agent and ship_symbol as arguments, or edit the values below
#
if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "9F"
    ship = f"{agent}-{ship_number}"
    behaviour_params = {"priority": 3, "target_sys": "X1-DJ15"}

    bhvr = WarpToSystem(agent, ship, behaviour_params or {})
    bhvr.ship = bhvr.st.ships_view_one(ship)
    lock_ship(ship, "MANUAL", bhvr.st.db_client.connection, 60 * 24)
    bhvr.run()
    lock_ship(ship, "MANUAL", bhvr.st.db_client.connection, 0)
