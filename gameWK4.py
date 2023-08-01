from behaviours.generic_behaviour import Behaviour
from straders_sdk import SpaceTraders
from straders_sdk.models import Waypoint
import math

BEHAVIOUR_NAME = "Explore local & jump network"


class Week4(Behaviour):
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
        # check all markets in the system
        unexplored_systems = [ship.nav.system_symbol]
        explored_systems = []

        # PING A JUMP GATE - get its systems
        # check if I've explored the system
        # do the waypoints have traits? no - add to list.
        # do the waypoints have traits? yes
        # are there any shipyards/ markets/ jump gates?
        # do I have details on them? - no - add to list
        # yes - skip
        # pick my nearest neighbour.
        # A* to it via jump gates.

        jump_gate = st.find_waypoint_by_type(ship.nav.system_symbol, "JUMP_GATE")
        if jump_gate:
            self.ship_intrasolar(jump_gate.symbol)
            jg = st.system_jumpgate(jump_gate)
            if not jg:
                print("jump gate not found?")
                return
            else:
                for system in jg.connected_waypoints:
                    print(system)

        else:
            print("system doesn't have a jump gate!")

    def scan_local_system(self):
        st = self.st
        ship = self.ship
        current_system_sym = self.ship.nav.system_symbol
        wayps = st.find_waypoints_by_trait(current_system_sym, "MARKETPLACE")
        wayps = wayps.extend(st.find_waypoints_by_trait(current_system_sym, "SHIPYARD"))
        wayps = wayps.extend(st.find_waypoint_by_type(current_system_sym, "JUMP_GATE"))

        start = st.waypoints_view_one(ship.nav.system_symbol, ship.nav.waypoint_symbol)
        path = nearest_neighbour(wayps, start)

        for wayp_sym in path:
            self.ship_intrasolar(wayp_sym)
            waypoint = st.waypoints_view_one(ship.nav.system_symbol, wayp_sym)
            if "MARKETPLACE" in waypoint.traits:
                market = st.system_market(waypoint)
                if market:
                    for listing in market.listings:
                        print(
                            f"item: {listing.symbol}, buy: {listing.purchase} sell: {listing.sell_price} - supply available {listing.supply}"
                        )
            if "SHIPYARD" in waypoint.traits:
                shipyard = st.system_shipyard(waypoint)
                if shipyard:
                    for ship in shipyard.ships:
                        print("ship")
            if waypoint.type == "JUMP_GATE":
                print("jump gate found!")


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


def calculate_distance(src: Waypoint, dest: Waypoint):
    return math.sqrt((src.x - dest.x) ** 2 + (src.y - dest.y) ** 2)


if __name__ == "__main__":
    Week4("CTRI", "CTRI-1").run()
