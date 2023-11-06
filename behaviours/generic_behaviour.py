import json
from straders_sdk import SpaceTraders
from time import sleep
from straders_sdk.ship import Ship
from straders_sdk.models import Waypoint, System, Market
from straders_sdk.local_response import LocalSpaceTradersRespose
from straders_sdk.utils import (
    set_logging,
    try_execute_select,
    waypoint_slicer,
    try_execute_upsert,
)
from straders_sdk.pathfinder import PathFinder, JumpGateRoute
import time
import logging
import math
import networkx
import heapq
import threading


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
        connection=None,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.behaviour_params = behaviour_params or {}

        saved_data = json.load(open(config_file_name, "r+"))
        token = None

        self._connection = connection
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
            connection=connection,
        )
        self.pathfinder = PathFinder(connection=self.connection)
        self.ship_name = ship_name
        self.ship = self.st.ships_view_one(ship_name)
        self._graph = None
        self.ships = None
        self.agent = None
        self.termination_event = threading.Event()

    @property
    def connection(self):
        if not self._connection or self._connection.closed > 0:
            self._connection = self.st.db_client.connection
        # self.logger.debug("connection PID: %s", self._connection.get_backend_pid())
        return self._connection

    def run(self):
        if not self.ship:
            self.ship = self.st.ships_view_one(self.ship_name, force=True)

            self.logger.error("error getting ship, aborting - %s", self.ship.error)
            raise Exception("error getting ship, aborting - %s", self.ship.error)
        self.st.ship_cooldown(self.ship)
        # get the cooldown info as well from the DB
        self.agent = self.st.view_my_self()

        pass

    def find_nearest_systems_by_waypoint_trait(
        self,
        source_system: System,
        trait: str,
        range: int = 50000,
        jumpgate_only=True,
    ) -> str:
        sql = """
            with source as (select src.x, src.y
            from systems src where system_Symbol  = %s
            )
            
            select s.system_symbol, s.x, s.y  
            , SQRT(POWER((s.x - source.x), 2) + POWER((s.y - source.y), 2)) AS distance
            from waypoint_traits wt
            join waypoints w on wt.waypoint_symbol = w.waypoint_symbol
            join systems s on s.system_symbol = w.system_symbol
            cross join source
            where wt.trait_symbol = %s
            and s.x between source.x - %s and source.x + %s
            and s.y between source.y - %s and source.y + %s
            order by distance asc 

        """
        results = try_execute_select(
            self.connection,
            sql,
            (
                source_system.symbol,
                trait,
                range,
                range,
                range,
                range,
            ),
        )

        if not jumpgate_only:
            return results[0][0]
        path = JumpGateRoute(None, None, 9999999, 999999, [], 0, None)

        for result in results:
            destination = System(result[0], None, None, result[1], result[2], None)
            route = self.pathfinder.astar(source_system, destination)
            if route and route.jumps < path.jumps:
                path = route
        return path.end_system if path.jumps < 999999 else None

    def ship_intrasolar(
        self, target_wp_symbol: "str", sleep_till_done=True, flight_mode="CRUISE"
    ):
        if isinstance(target_wp_symbol, Waypoint):
            target_wp_symbol = target_wp_symbol.symbol

        st = self.st
        ship = self.ship
        origin_waypoint = st.waypoints_view_one(
            ship.nav.system_symbol, ship.nav.waypoint_symbol
        )
        target_sys_symbol = waypoint_slicer(target_wp_symbol)
        if ship.nav.waypoint_symbol == target_wp_symbol:
            return LocalSpaceTradersRespose(
                error="Ship is already at the target waypoint",
                status_code=0,
                error_code=4204,
                url=f"{__name__}.ship_intrasolar",
            )
        if ship.nav.system_symbol != target_sys_symbol:
            return LocalSpaceTradersRespose(
                error="Ship is not in the same system as the target waypoint",
                status_code=0,
                error_code=4202,
                url=f"{__name__}.ship_intrasolar",
            )
        wp = self.st.waypoints_view_one(target_sys_symbol, target_wp_symbol)

        fuel_cost = self.pathfinder.determine_fuel_cost(origin_waypoint, wp)
        if (
            flight_mode != "DRIFT"
            and fuel_cost >= ship.fuel_current
            and ship.fuel_capacity > 0
            and fuel_cost < ship.fuel_capacity
        ):
            # need to refuel (note that satelites don't have a fuel tank, and don't need to refuel.)
            self.go_and_refuel()
        if (
            fuel_cost >= ship.fuel_current
            and ship.fuel_capacity > 0
            and ship.nav.flight_mode != "DRIFT"
        ):
            st.ship_patch_nav(ship, "DRIFT")
        elif ship.nav.flight_mode != flight_mode:
            st.ship_patch_nav(ship, flight_mode)

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
                ship.nav_dirty = True
                st.update(ship)
            self.logger.debug(
                "moved to %s, time to destination %s",
                ship.name,
                ship.nav.travel_time_remaining,
            )
            return resp
        return True

    def siphon_till_full(self, cutoff_cargo_units_used=None) -> Ship or bool:
        ship = self.ship
        st = self.st
        current_wayp = self.st.waypoints_view_one(
            self.ship.nav.system_symbol, self.ship.nav.waypoint_symbol
        )
        if current_wayp.type not in ("GAS_GIANT"):
            self.logger.error(
                "Ship is not at an siphonable location, sleeping then aborting"
            )
            sleep(300)
            return False
        cutoff_cargo_units_used = ship.cargo_capacity
        while ship.cargo_units_used < cutoff_cargo_units_used:
            cutoff_cargo_units_used = cutoff_cargo_units_used or ship.cargo_capacity

            # we've moved this to here because ofthen surveys expire after we select them whilst the ship is asleep.
            self.sleep_until_ready()

            resp = st.ship_siphon(ship)

            # extract. if we're full, return without refreshing the survey (as we won't use it)
            if ship.cargo_units_used >= cutoff_cargo_units_used:
                return ship

    def extract_till_full(
        self, cargo_to_target: list = None, cutoff_cargo_units_used=None
    ) -> Ship or bool:
        # need to validate that the ship'  s current WP is a valid location
        current_wayp = self.st.waypoints_view_one(
            self.ship.nav.system_symbol, self.ship.nav.waypoint_symbol
        )
        if current_wayp.type not in ("ASTEROID"):
            self.logger.error(
                "Ship is not at an extractable location, sleeping then aborting"
            )
            sleep(300)
            return False

        wayp_s = self.ship.nav.waypoint_symbol
        st = self.st
        if cargo_to_target is None:
            cargo_to_target = []
        if isinstance(cargo_to_target, str):
            cargo_to_target = [cargo_to_target]
        survey = None

        ship = self.ship
        st = self.st
        if ship.nav.status == "DOCKED":
            st.ship_orbit(ship)

        if len(cargo_to_target) > 0:
            survey = (
                st.find_survey_best_deposit(wayp_s, cargo_to_target[0])
                or st.find_survey_best(wayp_s)
                or None
            )
        else:
            survey = st.find_survey_best(self.ship.nav.waypoint_symbol) or None

        cutoff_cargo_units_used = ship.cargo_capacity
        while ship.cargo_units_used < cutoff_cargo_units_used:
            cutoff_cargo_units_used = cutoff_cargo_units_used or ship.cargo_capacity

            # we've moved this to here because ofthen surveys expire after we select them whilst the ship is asleep.
            self.sleep_until_ready()

            resp = st.ship_extract(ship, survey)

            # extract. if we're full, return without refreshing the survey (as we won't use it)
            if ship.cargo_units_used >= cutoff_cargo_units_used:
                return ship

            # 4224/4221 means exhausted survey - we can just try again and don't need to sleep.
            # 4000 means the ship is on cooldown (shouldn't happen, but safe to repeat attempt)
            if not resp and resp.error_code in [4228]:
                return False
            elif not resp and resp.error_code not in [4224, 4221, 4000]:
                return False
            else:
                # the survey is expired, refresh it.
                if len(cargo_to_target) > 0:
                    survey = (
                        st.find_survey_best_deposit(wayp_s, cargo_to_target[0])
                        or st.find_survey_best(wayp_s)
                        or None
                    )
                else:
                    survey = st.find_survey_best(self.ship.nav.waypoint_symbol) or None

    def go_and_refuel(self):
        ship = self.ship
        if ship.fuel_capacity == 0:
            return
        current_wayp = self.st.waypoints_view_one(
            ship.nav.system_symbol, ship.nav.waypoint_symbol
        )
        maybe_refuel_points = self.st.find_waypoints_by_trait(
            self.ship.nav.system_symbol, "MARKETPLACE"
        )

        if not maybe_refuel_points:
            self.st.waypoints_view(self.ship.nav.system_symbol, True)
            return LocalSpaceTradersRespose(
                "No refuel points found in system. We should go extrasolar", 0, 0, ""
            )
        nearest_refuel_wp = None
        nearest_refuel_distance = 99999
        for refuel_point in maybe_refuel_points:
            distance = self.pathfinder.calc_distance_between(current_wayp, refuel_point)
            if distance < nearest_refuel_distance:
                market = self.st.system_market(refuel_point)
                if market.get_tradegood("FUEL") is not None:
                    nearest_refuel_distance = distance
                    nearest_refuel_wp = refuel_point
        if nearest_refuel_wp is not None:
            flight_mode = ship.nav.flight_mode

            if (
                self.pathfinder.determine_fuel_cost(current_wayp, nearest_refuel_wp)
                > ship.fuel_current
            ):
                flight_mode = "DRIFT"
            self.ship_intrasolar(nearest_refuel_wp.symbol, flight_mode=flight_mode)
            self.st.ship_dock(ship)
            self.st.ship_refuel(ship)
            if flight_mode and flight_mode != ship.nav.flight_mode:
                self.st.ship_patch_nav(ship, flight_mode)

    def sell_all_cargo(self, exceptions: list = [], market: Market = None):
        ship = self.ship
        st = self.st
        listings = {}
        if not market:
            market = self.st.system_market(
                st.waypoints_view_one(ship.nav.system_symbol, ship.nav.waypoint_symbol)
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
            remaining_units = cargo.units
            for i in range(0, math.ceil(cargo.units / trade_volume)):
                resp = st.ship_sell(
                    ship, cargo.symbol, min(remaining_units, trade_volume)
                )
                remaining_units = remaining_units - trade_volume

                if not resp:
                    pass
                    # try the next cargo bit

        return True

    def find_adjacent_ships(self, waypoint_symbol: str, matching_roles: list):
        st = self.st
        if isinstance(matching_roles, str):
            matching_roles = [matching_roles]
        my_ships = st.ships_view()

        matching_ships = [
            ship for id, ship in my_ships.items() if ship.role in matching_roles
        ]
        valid_haulers = [
            ship
            for ship in matching_ships
            if ship.nav.waypoint_symbol == waypoint_symbol
        ]
        if len(valid_haulers) > 0:
            return valid_haulers
        return []

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

    def fulfil_any_relevant(self, excpetions: list = []):
        contracts = self.st.view_my_contracts()

        items = []
        tar_contract = None
        for contract in contracts:
            if contract.accepted and not contract.fulfilled:
                tar_contract = contract
                for deliverable in contract.deliverables:
                    if deliverable.units_fulfilled < deliverable.units_required:
                        items.append(deliverable)
        if len(items) == 0:
            return False

        if self.ship.nav.status != "DOCKED":
            self.st.ship_dock(self.ship)
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

    def find_best_market_systems_to_sell(
        self, trade_symbol: str
    ) -> list[(str, System, int)]:
        "returns market_waypoint, system obj, price as int"
        sql = """select sell_price, w.waypoint_symbol, s.system_symbol, s.sector_Symbol, s.type, s.x,s.y from market_tradegood_listings mtl 
join waypoints w on mtl.market_symbol = w.waypoint_Symbol
join systems s on w.system_symbol = s.system_symbol
where mtl.trade_symbol = %s
order by 1 desc """
        results = try_execute_select(self.connection, sql, (trade_symbol,))
        return_obj = []
        for row in results or []:
            sys = System(row[2], row[3], row[4], row[5], row[6], [])
            price = row[0]
            waypoint_symbol = row[1]

            return_obj.append((waypoint_symbol, sys, price))
        return return_obj

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

    def purchase_what_you_can(self, cargo_symbol: str, quantity: int):
        # check current waypoint has a market that sells the tradegood
        # check we have enough cargo space
        # check we have enough credits

        ship = self.ship
        current_waypoint = self.st.waypoints_view_one(
            ship.nav.system_symbol, ship.nav.waypoint_symbol
        )
        if "MARKETPLACE" not in [trait.symbol for trait in current_waypoint.traits]:
            return LocalSpaceTradersRespose(
                f"Waypoint {current_waypoint.symbol} is not a marketplace",
                0,
                0,
                "generic_behaviour.buy_cargo",
            )

        cargo_to_buy = min(quantity, ship.cargo_space_remaining)

        current_market = self.st.system_market(current_waypoint)
        if len(current_market.listings) == 0:
            current_market = self.st.system_market(current_waypoint, True)
        if cargo_symbol not in [l.symbol for l in current_market.listings]:
            return LocalSpaceTradersRespose(
                f"Waypoint {current_waypoint.symbol} does not have a listing for {cargo_symbol}",
                0,
                0,
                "generic_behaviour.buy_cargo",
            )
        found_listing = current_market.get_tradegood(cargo_symbol)

        current_credits = self.st.view_my_self().credits
        cargo_to_buy = min(
            cargo_to_buy, math.floor(current_credits / found_listing.purchase_price)
        )
        if cargo_to_buy == 0:
            return LocalSpaceTradersRespose(
                f"Ship {ship.name} cannot buy cargo because we're too poor",
                0,
                0,
                "generic_behaviour.purchase_what_you_can",
            )
        trade_volume = found_listing.trade_volume

        for i in range(math.ceil(cargo_to_buy / trade_volume)):
            resp = self.st.ship_purchase_cargo(
                ship, cargo_symbol, min(trade_volume, cargo_to_buy)
            )
            cargo_to_buy -= trade_volume
            if not resp:
                return resp
        return LocalSpaceTradersRespose(
            None, 0, 0, "generic_behaviour.purchase_what_you_can"
        )

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
        target_wayps = list(set(target_wayps))
        # remove dupes from target_wayps

        start = st.waypoints_view_one(ship.nav.system_symbol, ship.nav.waypoint_symbol)
        path = self.nearest_neighbour(target_wayps, start)

        for wayp_sym in path:
            waypoint = st.waypoints_view_one(ship.nav.system_symbol, wayp_sym)

            self.ship_intrasolar(wayp_sym)
            self.sleep_until_ready()
            trait_symbols = [trait.symbol for trait in waypoint.traits]
            if "MARKETPLACE" in trait_symbols:
                market = st.system_market(waypoint, True)
                if market:
                    for listing in market.listings:
                        print(
                            f"item: {listing.symbol}, buy: {listing.purchase_price} sell: {listing.sell_price} - supply available {listing.supply}"
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

    def ship_extrasolar(self, destination_system: System, route: JumpGateRoute = None):
        if isinstance(destination_system, str):
            self.logger.error("You passed a string not a system to ship_extrasolar")
            return False
        st = self.st
        ship = self.ship
        if ship.nav.system_symbol == destination_system.symbol:
            return True
        o_sys = st.systems_view_one(ship.nav.system_symbol)
        route = route or self.pathfinder.astar(o_sys, destination_system)
        if not route:
            self.logger.error(f"Unable to jump to {o_sys.symbol} - no route found")
            return None
        if ship.nav.system_symbol == destination_system.symbol:
            return True
        if ship.nav.status == "DOCKED":
            st.ship_orbit(ship)
        if ship.nav.travel_time_remaining > 0 or ship.seconds_until_cooldown > 0:
            self.sleep_until_ready()
        current_wp = st.waypoints_view_one(
            ship.nav.system_symbol, ship.nav.waypoint_symbol
        )
        self.st.logging_client.log_custom_event(
            "BEGIN_EXTRASOLAR_NAVIGATION",
            ship.name,
            {
                "origin_system": o_sys.symbol,
                "destination_system": destination_system.symbol,
                "route_length": (route.jumps),
            },
        )
        if current_wp.type != "JUMP_GATE":
            jg_wp = st.find_waypoints_by_type_one(ship.nav.system_symbol, "JUMP_GATE")
            resp = self.ship_intrasolar(jg_wp.symbol)
            if not resp:
                self.logger.warn("Unable to jump - not at warp gate.")
                return False
        route.route.pop(0)
        for next_sys in route.route:
            next_sys: System
            sleep(ship.seconds_until_cooldown)
            resp = st.ship_jump(ship, next_sys)
            if not resp:
                return resp
            if next_sys == destination_system.symbol:
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
                unplotted,
                key=lambda wp: self.pathfinder.calc_distance_between(current, wp),
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
                unplotted,
                key=lambda sys: self.pathfinder.calc_distance_between(current, sys),
            )
            path.append(next_system.symbol)
            unplotted.remove(next_system)
            current = next_system
        return path

    def end(self):
        if "task_hash" in self.behaviour_params:
            sql = """update ship_tasks set completed = true where task_hash = %s"""
            try_execute_upsert(
                self.connection, sql, (self.behaviour_params["task_hash"],)
            )
            time.sleep(20)
        # self.st.db_client.connection.close()
        # self.st.logging_client.connection.close()


def sleep_until_ready(ship: "Ship"):
    sleep(max(ship.seconds_until_cooldown, ship.nav.travel_time_remaining))
