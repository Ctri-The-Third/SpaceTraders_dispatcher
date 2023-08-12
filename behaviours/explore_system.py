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
        self.graph = self.populate_graph()
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
        if ship.nav.system_symbol != d_sys:
            arrived = self.ship_extrasolar(ship, d_sys)
        if not arrived:
            self.logger.error("Couldn't jump! Unknown reason.")
            return

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

    def populate_graph(self):
        graph = networkx.Graph()
        sql = """select s.symbol, s.sector_symbol, s.type, s.x, s.y from jump_gates jg 
join waypoints w on jg.waypoint_symbol = w.symbol
join systems s on w.system_symbol = s.symbol"""

        # the graph should be populated with Systems and Connections.
        # but note that the connections themselves need to by systems.
        # sql = """SELECT symbol, sector_symbol, type, x, y FROM systems"""
        # for row in rows:
        #    syst = System(row[0], row[1], row[2], row[3], row[4], [])

        results = try_execute_select(self.connection, sql, ())
        if results:
            nodes = {
                row[0]: System(row[0], row[1], row[2], row[3], row[4], [])
                for row in results
            }
            graph.add_nodes_from(nodes)

        else:
            return graph
        sql = """select w1.system_symbol, destination_waypoint from jumpgate_connections jc
                join waypoints w1 on jc.source_waypoint = w1.symbol
                """
        results = try_execute_select(self.connection, sql, ())
        connections = []
        for row in results:
            try:
                connections.append((nodes[row[0]], nodes[row[1]]))
            except KeyError:
                pass
                # this happens when the gate we're connected to is not one that we've scanned yet.
        if results:
            graph.add_edges_from(connections)
        return graph

    def ship_extrasolar(
        self, ship: "Ship", destination_system: System, route: list = None
    ):
        st = self.st
        o_sys = st.systems_view_one(ship.nav.system_symbol)
        route = route or astar(self.graph, o_sys, destination_system)
        if not route:
            self.logger.error(f"Unable to jump to {o_sys.symbol} - no route found")
            return None

        if ship.nav.status == "DOCKED":
            st.ship_orbit(ship)
        if ship.nav.travel_time_remaining > 0:
            time.sleep(ship.nav.travel_time_remaining)
        current_wp = st.waypoints_view_one(
            ship.nav.system_symbol, ship.nav.waypoint_symbol
        )
        if current_wp.type != "JUMP_GATE":
            jg_wp = st.find_waypoints_by_type_one(ship.nav.system_symbol, "JUMP_GATE")
            resp = self.ship_intrasolar(jg_wp.symbol)
            if not resp:
                self.logger.warn("Unable to jump - not at warp gate.")
                return False
        route.pop()
        for next_sys in route:
            next_sys: System
            st.ship_jump(ship, next_sys.symbol)
            time.sleep(ship.seconds_until_cooldown)
        # Then, hit it.care
        return True


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


def astar(graph: networkx.Graph, start: Waypoint, goal: Waypoint):
    if start not in graph.nodes:
        return None
    if goal not in graph.nodes:
        return None
    # freely admit used chatgpt to get started here.

    # Priority queue to store nodes based on f-score (priority = f-score)
    # C'tri note - I think this will be 1 for all edges?
    # Update - no, F-score is the distance between the specific node and the start
    open_set = []
    heapq.heappush(open_set, (0, start))

    # note to self - this dictionary is setting all g_scores to infinity- they have not been calculated yet.
    g_score = {node: float("inf") for node in graph.nodes}
    g_score[start] = 0

    # Data structure to store the f-score (g-score + heuristic) for each node
    f_score = {node: float("inf") for node in graph.nodes}
    f_score[start] = h(
        start, goal
    )  # heuristic function - standard straight-line X/Y distance

    # this is how we reconstruct our route back.Z came from Y. Y came from X. X came from start.
    came_from = {}
    while open_set:
        # Get the node with the lowest estimated total cost from the priority queue
        current = heapq.heappop(open_set)[1]
        # print(f"NEW NODE: {f_score[current]}")
        if current == goal:
            # first list item = destination
            total_path = [current]
            while current in came_from:
                # +1 list item = -1 from destination
                current = came_from[current]
                total_path.append(current)
            # reverse so frist list_item = source.
            logging.debug("Completed A* - total jumps = %s", len(total_path))
            return list(reversed(total_path))
            # Reconstruct the shortest path
            # the path will have been filled with every other step we've taken so far.

        for neighbour in graph.neighbors(current):
            # yes, g_score is the total number of jumps to get to this node.
            tentative_global_score = g_score[current] + 1

            if tentative_global_score < g_score[neighbour]:
                # what if the neighbour hasn't been g_scored yet?
                # ah we inf'd them, so unexplored is always higher
                # so if we're in here, neighbour is the one behind us.

                came_from[neighbour] = current
                g_score[neighbour] = tentative_global_score
                f_score[neighbour] = tentative_global_score + h(neighbour, goal)
                # print(f" checked: {f_score[neighbour]}")
                # this f_score part I don't quite get - we're storing number of jumps + remaining distance
                # I can't quite visualise but but if we're popping the lowest f_score in the heap - then we get the one that's closest?
                # which is good because if we had variable jump costs, that would be factored into the g_score - for example time.
                # actually that's a great point, time is the bottleneck we want to cut down on, not speed.
                # this function isn't built with that in mind tho so I'm not gonna bother _just yet_

                # add this neighbour to the priority queue - the one with the lowest remaining distance will be the next one popped.
                heapq.heappush(open_set, (f_score[neighbour], neighbour))

    return None


def h(start: System, goal: System):
    return ((start.x - goal.x) ** 2 + (start.y - goal.y) ** 2) ** 0.5


def calculate_distance(src: Waypoint, dest: Waypoint):
    return math.sqrt((src.x - dest.x) ** 2 + (src.y - dest.y) ** 2)


if __name__ == "__main__":
    set_logging(level=logging.DEBUG)
    agent_symbol = "CTRI-LWK5-"
    ship_suffix = "1"
    params = None
    #   params = {"asteroid_wp": "", "target_sys": "X1-FZ5"}
    ExploreSystem(agent_symbol, f"{agent_symbol}-{ship_suffix}", params).run()
