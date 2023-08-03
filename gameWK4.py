from behaviours.generic_behaviour import Behaviour
from straders_sdk import SpaceTraders
from straders_sdk.models import Waypoint, System
import math
import logging

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
        ships = st.ships_view(True)
        other_ships = st.ships_view()
        unexplored_systems = [ship.nav.system_symbol]
        explored_systems = []

        # PING A JUMP GATE - get its systems
        # check if I've explored the system
        # do the waypoints have traits? no - add to list.
        # do the waypoints have traits? yes
        # are there any shipyards/ markets/ jump gates?
        # do I have details on them? - no - add to list
        # Have I got the connceted systems?
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
                gate_wp = st.waypoints_view_one("X1-QR77", "X1-QR77-39247B")

        else:
            print("no jump gate found")
            return

        unexplored_systems = self.find_unexplored_jumpgate_systems()
        start = self.st.systems_view_one(ship.nav.system_symbol)
        order_to_visit = nearest_neighbour_systems(unexplored_systems, start)
        while order_to_visit:
            system = order_to_visit.pop(0)
            self.logger.info(
                f"About to explore {system}, remaining: {len(order_to_visit)}"
            )

            self.sleep_until_ready()
            jump_resp = self.st.ship_jump(ship, system)

            if ship.nav.system_symbol == system:
                starting_wp = ship.nav.waypoint_symbol
                self.scan_local_system()
                self.ship_intrasolar(starting_wp)
            else:
                self.logger.error(
                    f"Failed to jump to {system} because {jump_resp.error}"
                )
            # jump to system
            # explore system
            # return to gate

    def recursive_find_unexplored_systems(
        self, system_symbol: str, collected_system_symbols: list[str] = list()
    ) -> list[str]:
        # does the system have a warp gate? should be yes.
        # takes a good half hour. Might have limitations based on charting and not work straight away?
        resp = gate_wp = self.st.find_waypoint_by_type(system_symbol, "JUMP_GATE")
        if not resp:
            return collected_system_symbols

        gate = self.st.system_jumpgate(gate_wp)
        if not resp:
            return collected_system_symbols

        if system_symbol in collected_system_symbols:
            print(
                f"({len(collected_system_symbols)}){system_symbol} - Whoops, already got this system! "
            )
            return collected_system_symbols
        else:
            print(
                f"({len(collected_system_symbols)}){system_symbol} - adding and checking direct connects"
            )
            collected_system_symbols.append(system_symbol)
            for system in gate.connected_waypoints:
                self.recursive_find_unexplored_systems(
                    system.symbol, collected_system_symbols
                )

    def find_unexplored_jumpgate_systems(
        self,
    ) -> list[str]:
        sql = """
with mapped_systems as (
select s.symbol,  true as mapped 
from waypoints w 
join systems s on w.system_symbol=s.symbol 
join waypoint_traits wt on w.symbol = wt.waypoint
group by 1
having count(*) > 0
	)
select system_symbol, coalesce (mapped, false) as mapped, s.x, s.y
from jump_gates jg 
join waypoints w on jg.waypoint_symbol = w.symbol
left join mapped_systems ms on ms.symbol = w.symbol
left join systems s on system_symbol = s.symbol
where coalesce(mapped, false) = false;
"""
        try:
            cursor = self.st.db_client.connection.cursor()
            cursor.execute(sql, ())
            # fetch all rows
            resp = cursor.fetchall()
        except Exception as err:
            print(err)
            return []
        if not resp:
            return []
        unexplored_systems = []
        all_systems = self.st.systems_view_all()
        for row in resp:
            unexplored_systems.append(all_systems.get(row[0]))
        return unexplored_systems

    def scan_local_system(self):
        st = self.st
        ship = self.ship
        current_system_sym = self.ship.nav.system_symbol
        # situation - when loading the waypoints, we get the systemWaypoint aggregate that doesn't have traits or other info.
        # QUESTION
        st.waypoints_view(current_system_sym, True)
        target_wayps = st.find_waypoint_by_type(current_system_sym, "MARKETPLACE")

        target_wayps.extend(st.find_waypoints_by_trait(current_system_sym, "SHIPYARD"))
        target_wayps = target_wayps.extend(
            st.find_waypoint_by_type(current_system_sym, "JUMP_GATE")
        )

        start = st.waypoints_view_one(ship.nav.system_symbol, ship.nav.waypoint_symbol)
        path = nearest_neighbour(target_wayps, start)

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
                jump_gate = st.system_jumpgate(waypoint)


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
    Week4("CTRI-TEST-ALDV", "CTRI-TEST-ALDV-1").run()
