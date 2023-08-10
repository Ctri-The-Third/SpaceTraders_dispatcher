import sys

sys.path.append(".")
from behaviours.generic_behaviour import Behaviour
from straders_sdk import SpaceTraders
from straders_sdk.models import Waypoint, System
import math
import logging

BEHAVIOUR_NAME = "EXPLORE_ONE_SYSTEM"


class ExploreSystem(Behaviour):
    def __init__(
        self,
        agent_name,
        ship_name,
        behaviour_params: dict = ...,
        config_file_name="user.json",
    ) -> None:
        super().__init__(agent_name, ship_name, behaviour_params, config_file_name)

    def run(self):
        ship = self.ship
        st = self.st
        agent = st.view_my_self()
        # check all markets in the system
        tar_sys = self.behaviour_params["target_system"] or ship.nav.system_symbol

        st.logging_client.log_beginning(BEHAVIOUR_NAME, ship.name, agent.credits)

        if ship.nav.system_symbol != tar_sys:
            self.ship_extrasolar(tar_sys)
        self.scan_local_system()
        # travel to target system
        # scan target system

    def scan_local_system(self):
        st = self.st
        ship = self.ship
        current_system_sym = self.ship.nav.system_symbol
        # situation - when loading the waypoints, we get the systemWaypoint aggregate that doesn't have traits or other info.
        # QUESTION
        st.waypoints_view(current_system_sym, True)
        target_wayps = []
        marketplaces = (
            st.find_waypoints_by_trait(current_system_sym, "MARKETPLACE") or []
        )
        shipyards = st.find_waypoints_by_trait(current_system_sym, "SHIPYARD") or []
        gate = st.find_waypoints_by_type_one(current_system_sym, "JUMP_GATE")
        target_wayps.extend(marketplaces)
        target_wayps.extend(shipyards)
        target_wayps.append(gate)

        start = st.waypoints_view_one(ship.nav.system_symbol, ship.nav.waypoint_symbol)
        path = nearest_neighbour(target_wayps, start)

        for wayp_sym in path:
            waypoint = st.waypoints_view_one(ship.nav.system_symbol, wayp_sym)

            self.ship_intrasolar(wayp_sym)

            trait_symbols = [trait.symbol for trait in waypoint.traits]
            if "MARKETPLACE" in trait_symbols:
                market = st.system_market(waypoint, True)
                if market:
                    for listing in market.listings:
                        print(
                            f"item: {listing.symbol}, buy: {listing.purchase} sell: {listing.sell_price} - supply available {listing.supply}"
                        )
            if "SHIPYARD" in trait_symbols:
                shipyard = st.system_shipyard(waypoint, True)
                if shipyard:
                    for ship_type in shipyard.ship_types:
                        print(ship_type)
            if waypoint.type == "JUMP_GATE":
                jump_gate = st.system_jumpgate(waypoint, True)


def nearest_neighbour(waypoints: list[Waypoint], start: Waypoint):
    path = []
    unplotted = waypoints
    current = start
    while unplotted:  # whlist there are unplotted waypoints needing visited
        # note that we are not iterating over the contents, so it's safe to delete from the inside.

        # find the closest waypoint.
        # for each entry in unplotted,
        #   pass it as "wp" to the calculate_distance function
        #   return the minimum value of those returned by the function.
        next_waypoint = min(unplotted, key=lambda wp: calculate_distance(current, wp))
        path.append(next_waypoint.symbol)
        unplotted.remove(next_waypoint)
        current = next_waypoint
    return path


def nearest_neighbour_systems(systems: list[System], start: System):
    path = []
    unplotted = systems
    current = start
    while unplotted:
        next_system = min(unplotted, key=lambda sys: calculate_distance(current, sys))
        path.append(next_system.symbol)
        unplotted.remove(next_system)
        current = next_system
    return path


def calculate_distance(src: Waypoint, dest: Waypoint):
    return math.sqrt((src.x - dest.x) ** 2 + (src.y - dest.y) ** 2)


if __name__ == "__main__":
    ExploreSystem("CTRI-TEST-ALDV", "CTRI-TEST-ALDV-1").run()
