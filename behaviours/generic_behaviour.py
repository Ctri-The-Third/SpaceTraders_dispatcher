import json
from straders_sdk import SpaceTraders
from time import sleep
from straders_sdk.ship import Ship
from straders_sdk.models import Waypoint, System, Market
from straders_sdk.local_response import LocalSpaceTradersRespose
from straders_sdk.utils import set_logging, try_execute_select, waypoint_slicer
import logging
import math
import networkx
import heapq


class Behaviour:
    st: SpaceTraders
    ship: Ship

    def __init__(
        self,
        agent_name,
        ship_name,
        behaviour_params: dict = {},
        config_file_name="user.json",
        session=None,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.behaviour_params = behaviour_params or {}
        saved_data = json.load(open(config_file_name, "r+"))
        token = None
        self.ship_name = ship_name
        for agent in saved_data["agents"]:
            if agent.get("username", "") == agent_name:
                token = agent["token"]
                break
        if not token:
            # register the user
            pass
        db_host = saved_data.get("db_host", None)
        db_port = saved_data.get("db_port", None)
        db_name = saved_data.get("db_name", None)
        db_user = saved_data.get("db_user", None)
        db_pass = saved_data.get("db_pass", None)
        self.st = SpaceTraders(
            token,
            db_host=db_host,
            db_port=db_port,
            db_name=db_name,
            db_user=db_user,
            db_pass=db_pass,
            current_agent_symbol=agent_name,
            session=session,
        )
        self._connection = None
        self.graph = None
        self.ships = None
        self.agent = None

    @property
    def connection(self):
        if not self._connection or self._connection.closed > 0:
            self._connection = self.st.db_client.connection
        return self._connection

    def run(self):
        self.graph = self._populate_graph()

        self.ship = self.st.ships_view_one(self.ship_name, force=True)
        if not self.ship:
            self.logger.error("error getting ship, aborting - %s", self.ship.error)
            raise Exception("error getting ship, aborting - %s", self.ship.error)
        self.st.ship_cooldown(self.ship)
        # get the cooldown info as well from the DB
        self.agent = self.st.view_my_self()

        pass

    def ship_intrasolar(
        self, target_wp_symbol: "str", sleep_till_done=True, flight_mode="CRUISE"
    ):
        if isinstance(target_wp_symbol, Waypoint):
            target_wp_symbol = target_wp_symbol.symbol
        st = self.st
        ship = self.ship

        if ship.nav.system_symbol != waypoint_slicer(target_wp_symbol):
            return LocalSpaceTradersRespose(
                error="Ship is not in the same system as the target waypoint",
                status_code=0,
                error_code=4202,
                url=f"{__name__}.ship_intrasolar",
            )

        if ship.nav.flight_mode != flight_mode:
            st.ship_patch_nav(ship, flight_mode)
        wp = self.st.waypoints_view_one(ship.nav.system_symbol, target_wp_symbol)

        fuel_cost = self.determine_fuel_cost(self.ship, wp)
        if (
            flight_mode != "DRIFT"
            and fuel_cost > ship.fuel_current
            and ship.fuel_capacity > 0
        ):
            # need to refuel (note that satelites don't have a fuel tank, and don't need to refuel.)

            self.go_and_refuel()
        if ship.nav.waypoint_symbol != target_wp_symbol:
            if ship.nav.status == "DOCKED":
                st.ship_orbit(self.ship)

            resp = st.ship_move(self.ship, target_wp_symbol)
            if not resp:
                return False
            if sleep_till_done:
                sleep_until_ready(self.ship)
                ship.nav.status = "IN_ORBIT"
                ship.nav.waypoint_symbol = target_wp_symbol
                st.update(ship)
            self.logger.debug(
                "moved to %s, time to destination %s",
                ship.name,
                ship.nav.travel_time_remaining,
            )
            return resp
        return True

    def extract_till_full(self, cargo_to_target: list = None):
        # need to validate that the ship'  s current WP is a valid location
        current_wayp = self.st.waypoints_view_one(
            self.ship.nav.system_symbol, self.ship.nav.waypoint_symbol
        )
        if current_wayp.type != "ASTEROID_FIELD":
            self.logger.error(
                "Ship is not in an asteroid field, sleeping then aborting"
            )
            sleep(300)
            return False

        wayp_s = self.ship.nav.waypoint_symbol
        st = self.st
        if cargo_to_target is None:
            cargo_to_target = []
        survey = None

        ship = self.ship
        st = self.st
        if ship.nav.status == "DOCKED":
            st.ship_orbit(ship)
        while ship.cargo_units_used < ship.cargo_capacity:
            if len(cargo_to_target) > 0:
                survey = (
                    st.find_survey_best_deposit(wayp_s, cargo_to_target[0])
                    or st.find_survey_best(wayp_s)
                    or None
                )
            else:
                survey = st.find_survey_best(self.ship.nav.waypoint_symbol) or None
            if ship.seconds_until_cooldown > 0:  # we're coming into this already on CD
                sleep(ship.seconds_until_cooldown)
            resp = st.ship_extract(ship, survey)
            if ship.cargo_units_used == ship.cargo_capacity:
                return
            if not resp:
                sleep(30)
                return
                # ship is probably stuck in this state forever
            else:
                sleep_until_ready(self.ship)

    def go_and_refuel(self):
        ship = self.ship
        if ship.fuel_capacity == 0:
            return
        refuel_points = self.st.find_waypoints_by_trait(
            self.ship.nav.system_symbol, "MARKETPLACE"
        )
        if not refuel_points:
            self.st.waypoints_view(self.ship.nav.system_symbol, True)
            return LocalSpaceTradersRespose(
                "No refuel points found in system. We should go extrasolar", 0, 0, ""
            )
        nearest_refuel_wp = None
        nearest_refuel_distance = 99999
        for refuel_point in refuel_points:
            distance = self.distance_from_ship(ship, refuel_point)
            if distance < nearest_refuel_distance:
                nearest_refuel_distance = distance
                nearest_refuel_wp = refuel_point
        if nearest_refuel_wp is not None:
            flight_mode = ship.nav.flight_mode

            if self.determine_fuel_cost(ship, nearest_refuel_wp) > ship.fuel_current:
                flight_mode = "DRIFT"
            self.ship_intrasolar(nearest_refuel_wp.symbol, flight_mode=flight_mode)
            self.st.ship_dock(ship)
            self.st.ship_refuel(ship)
            if flight_mode:
                self.st.ship_patch_nav(ship, flight_mode)

    def sell_all_cargo(self, exceptions: list = [], market: Market = None):
        ship = self.ship
        st = self.st
        listings = {}
        if not market:
            market = self.st.system_market(
                st.waypoints_view_one(ship.nav.system_symbol, ship.nav.waypoint_symbol),
                True,
            )
        if market:
            listings = {listing.symbol: listing for listing in market.listings}
        if ship.nav.status != "DOCKED":
            st.ship_dock(ship)
        for cargo in ship.cargo_inventory:
            if cargo.symbol in exceptions:
                continue
            # we need to validate that we're not selling more than the tradegood volume for the market allows.
            listing = listings.get(cargo.symbol, None)
            trade_volume = cargo.units
            if listing:
                trade_volume = listing.trade_volume
            for i in range(0, math.ceil(cargo.units / trade_volume)):
                resp = st.ship_sell(ship, cargo.symbol, min(cargo.units, trade_volume))
                if not resp:
                    return resp

        return True

    def jettison_all_cargo(self, exceptions: list = []):
        ship = self.ship
        st = self.st

        for cargo in ship.cargo_inventory:
            if cargo.symbol in exceptions:
                continue
            resp = st.ship_jettison_cargo(ship, cargo.symbol, cargo.units)
            if not resp:
                return resp
        return True

    def fulfill_any_relevant(self, excpetions: list = []):
        contracts = self.st.view_my_contracts()

        items = []
        tar_contract = None
        for contract_id, contract in contracts.items():
            if contract.accepted and not contract.fulfilled:
                tar_contract = contract
                for deliverable in contract.deliverables:
                    if deliverable.units_fulfilled < deliverable.units_required:
                        items.append(deliverable)

        for cargo in self.ship.cargo_inventory:
            matching_items = [item for item in items if item.symbol == cargo.symbol]
        if not matching_items:
            logging.warning(
                "ship doesn't have any items matching deliverables to deliver"
            )
            return LocalSpaceTradersRespose(
                "Cargo doesn't have any matching items.",
                0,
                0,
                "generic_behaviour.fulfill_any_relevant",
            )
        cargo_to_deliver = min(matching_items[0].units_required, cargo.units)
        return self.st.contracts_deliver(
            tar_contract, self.ship, cargo.symbol, cargo_to_deliver
        )

    def buy_cargo(self, cargo_symbol: str, quantity: int):
        # check the waypoint we're at has a market
        # check the market has the cargo symbol we're seeking
        # check the market_depth is sufficient, buy until quantity hit.

        ship = self.ship
        st = self.st
        current_waypoint = st.waypoints_view_one(
            ship.nav.system_symbol, ship.nav.waypoint_symbol
        )
        if "MARKETPLACE" not in [trait.symbol for trait in current_waypoint.traits]:
            return LocalSpaceTradersRespose(
                f"Waypoint {current_waypoint.symbol} is not a marketplace",
                0,
                0,
                "generic_behaviour.buy_cargo",
            )

        if ship.nav.status != "DOCKED":
            st.ship_dock(ship)

        current_market = st.system_market(current_waypoint)
        if len(current_market.listings) == 0:
            current_market = st.system_market(current_waypoint, True)

        found_listing = None
        for listing in current_market.listings:
            if listing.symbol == cargo_symbol:
                found_listing = listing

        if not found_listing:
            return LocalSpaceTradersRespose(
                f"Waypoint {current_waypoint.symbol} does not have a listing for {cargo_symbol}",
                0,
                0,
                "generic_behaviour.buy_cargo",
            )
        amount_to_buy = ship.cargo_capacity - ship.cargo_units_used
        if amount_to_buy == 0:
            return LocalSpaceTradersRespose(
                f"Ship {ship.name} has no cargo capacity remaining",
                0,
                0,
                "generic_behaviour.buy_cargo",
            )

        times_to_buy = math.ceil(quantity / found_listing.trade_volume)
        for i in range(0, times_to_buy):
            resp = st.ship_purchase_cargo(
                ship, cargo_symbol, found_listing.trade_volume
            )
            if not resp:
                return resp
        return True

    def scan_local_system(self):
        st = self.st
        ship = self.ship
        current_system_sym = self.ship.nav.system_symbol
        flight_mode = "CRUISE" if ship.fuel_capacity > 0 else "BURN"
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
        path = self.nearest_neighbour(target_wayps, start)

        for wayp_sym in path:
            waypoint = st.waypoints_view_one(ship.nav.system_symbol, wayp_sym)

            self.ship_intrasolar(wayp_sym, flight_mode=flight_mode)

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

    def sleep_until_ready(self):
        sleep_until_ready(self.ship)

    def determine_fuel_cost(self, ship: "Ship", target_wp: "Waypoint") -> int:
        st = self.st
        source = st.waypoints_view_one(ship.nav.system_symbol, ship.nav.waypoint_symbol)

        speed = {"CRUISE": 1, "DRIFT": 0, "BURN": 2, "STEALTH": 1}
        return int(
            max(
                distance_between_wps(source, target_wp) * speed[ship.nav.flight_mode], 1
            )
        )

    def determine_travel_time(self, ship: "Ship", target_wp: "Waypoint") -> int:
        st = self.st
        source = st.waypoints_view_one(ship.nav.system_symbol, ship.nav.waypoint_symbol)

        distance = math.sqrt(
            (target_wp.x - source.x) ** 2 + (target_wp.y - source.y) ** 2
        )
        multiplier = {"CRUISE": 15, "DRIFT": 150, "BURN": 7.5, "STEALTH": 30}
        (
            math.floor(round(max(1, distance)))
            * (multiplier[ship.nav.flight_mode] / ship.engine.speed)
            + 15
        )

    def distance_from_ship(self, ship: Ship, target_wp: Waypoint) -> float:
        source = self.st.waypoints_view_one(
            ship.nav.system_symbol, ship.nav.waypoint_symbol
        )
        return distance_between_wps(source, target_wp)

    def ship_extrasolar(self, destination_system: System, route: list = None):
        if isinstance(destination_system, str):
            self.logger.error("You passed a string not a system to ship_extrasolar")
            return False
        st = self.st
        ship = self.ship
        if ship.nav.system_symbol == destination_system.symbol:
            return True
        o_sys = st.systems_view_one(ship.nav.system_symbol)
        route = route or self.astar(self.graph, o_sys, destination_system)
        if not route:
            self.logger.error(f"Unable to jump to {o_sys.symbol} - no route found")
            return None
        if ship.nav.system_symbol == destination_system.symbol:
            return True
        if ship.nav.status == "DOCKED":
            st.ship_orbit(ship)
        if ship.nav.travel_time_remaining > 0 or ship.seconds_until_cooldown > 0:
            sleep(max(ship.nav.travel_time_remaining, ship.seconds_until_cooldown))
        current_wp = st.waypoints_view_one(
            ship.nav.system_symbol, ship.nav.waypoint_symbol
        )
        if current_wp.type != "JUMP_GATE":
            jg_wp = st.find_waypoints_by_type_one(ship.nav.system_symbol, "JUMP_GATE")
            resp = self.ship_intrasolar(jg_wp.symbol)
            if not resp:
                self.logger.warn("Unable to jump - not at warp gate.")
                return False
        route.pop(0)
        for next_sys in route:
            next_sys: System
            sleep(ship.seconds_until_cooldown)
            resp = st.ship_jump(ship, next_sys.symbol)
            if not resp:
                return resp
            if next_sys.symbol == destination_system.symbol:
                # we've arrived, no need to sleepx
                break

        # Then, hit it.care
        return True

    def nearest_neighbour(self, waypoints: list[Waypoint], start: Waypoint):
        path = []
        unplotted = waypoints
        current = start
        while unplotted:  # whlist there are unplotted waypoints needing visited
            # note that we are not iterating over the contents, so it's safe to delete from the inside.

            # find the closest waypoint.
            # for each entry in unplotted,
            #   pass it as "wp" to the calculate_distance function
            #   return the minimum value of those returned by the function.
            next_waypoint = min(
                unplotted, key=lambda wp: calculate_distance(current, wp)
            )
            path.append(next_waypoint.symbol)
            unplotted.remove(next_waypoint)
            current = next_waypoint
        return path

    def nearest_neighbour_systems(self, systems: list[System], start: System):
        path = []
        unplotted = systems
        current = start
        while unplotted:
            next_system = min(
                unplotted, key=lambda sys: calculate_distance(current, sys)
            )
            path.append(next_system.symbol)
            unplotted.remove(next_system)
            current = next_system
        return path

    def astar(
        self,
        graph: networkx.Graph,
        start: Waypoint or System,
        goal: Waypoint or System,
        bypass_check: bool = False,
    ):
        if not bypass_check:
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
        f_score[start] = self.h(
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
                    f_score[neighbour] = tentative_global_score + self.h(
                        neighbour, goal
                    )
                    # print(f" checked: {f_score[neighbour]}")
                    # this f_score part I don't quite get - we're storing number of jumps + remaining distance
                    # I can't quite visualise but but if we're popping the lowest f_score in the heap - then we get the one that's closest?
                    # which is good because if we had variable jump costs, that would be factored into the g_score - for example time.
                    # actually that's a great point, time is the bottleneck we want to cut down on, not speed.
                    # this function isn't built with that in mind tho so I'm not gonna bother _just yet_

                    # add this neighbour to the priority queue - the one with the lowest remaining distance will be the next one popped.
                    heapq.heappush(open_set, (f_score[neighbour], neighbour))

        return None

    def h(self, start: Waypoint or System, goal: Waypoint or System):
        return ((start.x - goal.x) ** 2 + (start.y - goal.y) ** 2) ** 0.5

    def _populate_graph(self):
        graph = networkx.Graph()
        sql = """select distinct s.system_symbol, s.sector_symbol, s.type, s.x, s.y from jumpgate_connections jc 
join systems s on jc.d_waypoint_symbol = s.system_symbol
order by 1 
"""

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
        sql = """select w1.system_symbol, jc.d_waypoint_symbol from jumpgate_connections jc
                join waypoints w1 on jc.s_waypoint_symbol = w1.waypoint_symbol
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


def calculate_distance(src: Waypoint, dest: Waypoint):
    return math.sqrt((src.x - dest.x) ** 2 + (src.y - dest.y) ** 2)


def sleep_until_ready(ship: "Ship"):
    sleep(max(ship.seconds_until_cooldown, ship.nav.travel_time_remaining))


def distance_between_wps(source: Waypoint, target_wp: Waypoint) -> float:
    return math.sqrt((target_wp.x - source.x) ** 2 + (target_wp.y - source.y) ** 2)
