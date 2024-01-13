import json
from straders_sdk import SpaceTraders
from time import sleep
from straders_sdk.ship import Ship
from straders_sdk.models import Waypoint, System, Market, MarketTradeGoodListing
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
import os

SAFETY_PADDING = 60


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
        if connection:
            self.logger.warning(
                "you're passing the connection in again, shouldn't be doing that. "
            )
        saved_data = json.load(open(config_file_name, "r+"))
        token = None
        self.priority = self.behaviour_params.get("priority", 5)
        for agent in saved_data["agents"]:
            if agent.get("username", "") == agent_name:
                token = agent["token"]
                break
        if not token:
            # register the user
            pass
        db_host = os.environ.get("ST_DB_HOST", None)
        db_port = os.environ.get("ST_DB_PORT", None)
        db_name = os.environ.get("ST_DB_NAME", None)
        db_user = os.environ.get("ST_DB_USER", None)
        db_pass = os.environ.get("ST_DB_PASS", None)
        if not db_pass:
            db_pass = os.environ.get("ST_DB_PASSWORD", None)
        self.st = SpaceTraders(
            token,
            db_host=db_host,
            db_port=db_port,
            db_name=db_name,
            db_user=db_user,
            db_pass=db_pass,
            current_agent_symbol=agent_name,
            session=session,
            priority=self.priority,
        )
        self.pathfinder = PathFinder()
        self.ship_name = ship_name
        self.ship = None
        self._graph = None
        self.ships = None
        self.agent = None
        self.termination_event = threading.Event()

    @property
    def connection(self):
        return self.st.connection

    def run(self):
        self.ship = self.st.ships_view_one(self.ship_name)

        delay_start = self.behaviour_params.get("delay_start", 0)
        if self.ship.cargo_units_used != sum(
            [c.units for c in self.ship.cargo_inventory]
        ):
            self.ship = self.st.ships_view_one(self.ship_name, force=True)
        if not self.ship:
            self.logger.error("error getting ship, aborting - %s", self.ship.error)
            raise Exception("error getting ship, aborting - %s", self.ship.error)
        self.st.ship_cooldown(self.ship)
        # self.sleep_until_ready()
        self.st.sleep(delay_start)
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
            sql,
            (
                source_system.symbol,
                trait,
                range,
                range,
                range,
                range,
            ),
            self.connection,
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
        self,
        target_wp_symbol: "str",
        sleep_till_done=True,
        flight_mode=None,
        route=None,
    ):
        if isinstance(target_wp_symbol, Waypoint):
            target_wp_symbol = target_wp_symbol.symbol

        st = self.st
        ship = self.ship
        origin_wp = st.waypoints_view_one(ship.nav.waypoint_symbol)
        target_sys_symbol = waypoint_slicer(target_wp_symbol)
        if ship.nav.waypoint_symbol == target_wp_symbol:
            if ship.nav.status == "IN_TRANSIT":
                self.sleep_until_arrived()
            else:
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
        dest_wp = self.st.waypoints_view_one(target_wp_symbol)
        route = route or self.pathfinder.plot_system_nav(
            ship.nav.system_symbol,
            origin_wp,
            dest_wp,
            self.ship.fuel_capacity,
        )
        if not route:
            route = [dest_wp]
            self.logger.warning(
                "COULDN'T PLOT ROUTE this shouldn't happen - going direct from %s to %s",
                origin_wp.symbol,
                dest_wp.symbol,
            )
        current_wp = origin_wp
        for point_s in route.route:
            if isinstance(point_s, Waypoint):
                point = point_s
                point_s = point.symbol
            point_s: str
            if point_s == current_wp.symbol:
                continue
            point = self.st.waypoints_view_one(point_s)
            temp_flight_mode = flight_mode

            if not temp_flight_mode:
                temp_flight_mode = self.pathfinder.determine_best_speed(
                    current_wp, point, ship.fuel_capacity
                )
            fuel_cost = self.pathfinder.determine_fuel_cost(
                current_wp, point, temp_flight_mode
            )
            attempts = 0
            while (
                (flight_mode is None or temp_flight_mode != "DRIFT")
                and fuel_cost >= ship.fuel_current
                and (ship.fuel_capacity > 0 or ship.fuel_current <= 5)
                and fuel_cost < ship.fuel_capacity
                and attempts < 5
            ) or (ship.fuel_capacity > 0 and ship.fuel_current <= 5):
                # need to refuel (note that satelites don't have a fuel tank, and don't need to refuel.)
                attempts += 1
                resp = self.refuel_locally()
                if not resp and resp.error_code == 4600:  # not enough credits
                    self.st.sleep(60)
                    pass

                elif not resp:
                    # recalculate best speed, maybe we can drop down to CRUISE rather than have to DRIFT
                    if not flight_mode:
                        temp_flight_mode = self.pathfinder.determine_best_speed(
                            current_wp, point, ship.fuel_current
                        )
                        fuel_cost = self.pathfinder.determine_fuel_cost(
                            current_wp, point, temp_flight_mode
                        )
                    break

            if (
                fuel_cost >= ship.fuel_current
                and ship.fuel_capacity > 0
                and ship.nav.flight_mode != "DRIFT"
            ):
                self.logger.warn(
                    "DRIFT ALERT - Cached values: Current fuel %s, fuel cost %s, route = %s",
                    ship.fuel_current,
                    fuel_cost,
                    [w for w in route.route],
                )
                st.ship_patch_nav(ship, "DRIFT")
            elif ship.nav.flight_mode != temp_flight_mode:
                st.ship_patch_nav(ship, temp_flight_mode)

            if ship.nav.waypoint_symbol != point.symbol:
                if ship.nav.status == "DOCKED":
                    st.ship_orbit(self.ship)

                resp = st.ship_move(self.ship, point.symbol)
                if not resp:
                    return resp
                if sleep_till_done:
                    self.sleep_until_arrived()
                    ship.nav.status = "IN_ORBIT"
                    ship.nav.waypoint_symbol = point.symbol
                    ship.nav_dirty = True
                    st.update(ship)
                self.logger.debug(
                    "moved to %s, time to destination %s",
                    ship.name,
                    ship.nav.travel_time_remaining,
                )
                current_wp = point

        return True

    def route_to_nearest_marketplace(self, waypoint_symbol: str, fuel_capacity: int):
        current_location = self.st.waypoints_view_one(waypoint_symbol)
        wayps = self.st.find_waypoints_by_trait(
            waypoint_slicer(waypoint_symbol), "MARKETPLACE"
        )
        if not wayps:
            return None
        # sort the wayps by distance
        wayps = sorted(
            wayps,
            key=lambda x: self.pathfinder.calc_distance_between(current_location, x),
        )
        return self.pathfinder.plot_system_nav(
            current_location.system_symbol,
            current_location,
            wayps[0],
            fuel_capacity,
        )

    def siphon_till_full(
        self, cutoff_cargo_units_used=None, tradegoods_to_discard: list[str] = None
    ) -> Ship or bool:
        ship = self.ship
        st = self.st
        current_wayp = self.st.waypoints_view_one(self.ship.nav.waypoint_symbol)
        if tradegoods_to_discard is None:
            tradegoods_to_discard = []

        if current_wayp.type not in ("GAS_GIANT"):
            self.logger.error(
                "Ship is not at an siphonable location, sleeping then aborting"
            )
            sleep(300)
            return False
        if ship.nav.status == "DOCKED":
            st.ship_orbit(ship)

        cutoff_cargo_units_used = ship.cargo_capacity
        while ship.cargo_units_used < cutoff_cargo_units_used:
            cutoff_cargo_units_used = cutoff_cargo_units_used or ship.cargo_capacity

            # we've moved this to here because ofthen surveys expire after we select them whilst the ship is asleep.
            self.sleep_until_ready()

            resp = st.ship_siphon(ship)
            if not resp and resp.error_code == 4228:
                return False
            for cargo in ship.cargo_inventory:
                if cargo.symbol in tradegoods_to_discard:
                    st.ship_jettison_cargo(ship, cargo.symbol, cargo.units)

            # extract. if we're full, return without refreshing the survey (as we won't use it)
            if ship.cargo_units_used >= cutoff_cargo_units_used:
                return ship

    def extract_till_full(
        self,
        cargo_to_target: list = None,
        cargo_to_discard: list = None,
        cutoff_cargo_units_used=None,
    ) -> Ship or bool:
        # need to validate that the ship'  s current WP is a valid location
        current_wayp = self.st.waypoints_view_one(self.ship.nav.waypoint_symbol)
        if current_wayp.type not in ("ASTEROID", "ENGINEERED_ASTEROID"):
            self.logger.error(
                "Ship is not at an extractable location, sleeping then aborting"
            )
            sleep(300)
            return False

        wayp_s = self.ship.nav.waypoint_symbol
        wayp = self.st.waypoints_view_one(wayp_s)
        if "UNSTABLE" in wayp.modifiers:
            self.logger.error("asteroid %s still unstable, aborting", wayp_s)
            sleep(SAFETY_PADDING * 3)
            return False
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
        resp = True
        while ship.cargo_units_used < cutoff_cargo_units_used and resp:
            cutoff_cargo_units_used = cutoff_cargo_units_used or ship.cargo_capacity

            # we've moved this to here because ofthen surveys expire after we select them whilst the ship is asleep.
            self.sleep_until_ready()

            resp = st.ship_extract(ship, survey)

            if cargo_to_discard:
                for cargo in ship.cargo_inventory:
                    if cargo.symbol in cargo_to_discard:
                        st.ship_jettison_cargo(ship, cargo.symbol, cargo.units)
            # extract. if we're full, return without refreshing the survey (as we won't use it)
            if ship.cargo_units_used >= cutoff_cargo_units_used:
                return ship

            # 4224/4221 means exhausted survey - we can just try again and don't need to sleep.
            # 4000 means the ship is on cooldown (shouldn't happen, but safe to repeat attempt)
            if not resp and resp.error_code in [4228]:
                return False
            elif not resp and resp.error_code == 4253:
                wayp = self.st.waypoints_view_one(self.ship.nav.waypoint_symbol)
                if "UNSTABLE" not in wayp.modifiers:
                    wayp.modifiers.append("UNSTABLE")
                    self.st.update(wayp)
                self.logger.error("ASTEROID UNSTABLE, CONDUCTOR SHOULD ABORT.")
                sleep(SAFETY_PADDING * 3)
                return False
            elif not resp and resp.error_code not in [4224, 4221, 4000]:
                return False
            else:
                # the survey is expired, refresh it.]
                resp = True
                if len(cargo_to_target) > 0:
                    survey = (
                        st.find_survey_best_deposit(wayp_s, cargo_to_target[0])
                        or st.find_survey_best(wayp_s)
                        or None
                    )
                else:
                    survey = st.find_survey_best(self.ship.nav.waypoint_symbol) or None

    def refuel_locally(self):
        ship = self.ship
        if ship.fuel_capacity == 0:
            return
        if ship.nav.status != "DOCKED":
            self.st.ship_dock(ship)
        resp = self.st.ship_refuel(ship)
        if not resp:
            self.logger.error("error refueling ship %s", resp.error)
        return resp

        # this used to be "go and refuel."
        # in order try and understand why ships are sometimes drifting, and to take advantage
        # of the fuel-aware pathfinder, we're simplifying this.
        current_wayp = self.st.waypoints_view_one(ship.nav.waypoint_symbol)
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
        flight_mode = ship.nav.flight_mode
        if current_wayp not in maybe_refuel_points:
            for refuel_point in maybe_refuel_points:
                distance = self.pathfinder.calc_distance_between(
                    current_wayp, refuel_point
                )
                if distance < nearest_refuel_distance:
                    market = self.st.system_market(refuel_point)
                    if market.get_tradegood("FUEL") is not None:
                        nearest_refuel_distance = distance
                        nearest_refuel_wp = refuel_point

            if (
                self.pathfinder.determine_fuel_cost(current_wayp, nearest_refuel_wp)
                >= ship.fuel_current
            ):
                flight_mode = "DRIFT"
            if distance >= 0:
                self.ship_intrasolar(nearest_refuel_wp.symbol, flight_mode=flight_mode)

        else:
            nearest_refuel_wp = current_wayp
            nearest_refuel_distance = 0
        if nearest_refuel_wp is not None:
            self.st.ship_dock(ship)
            self.st.ship_refuel(ship)
            if flight_mode and flight_mode != ship.nav.flight_mode:
                self.st.ship_patch_nav(ship, flight_mode)

    def sell_cargo(self, cargo_symbol: str, quantity: int, market: Market = None):
        ship = self.ship
        st = self.st

        cargo = [ci for ci in ship.cargo_inventory if ci.symbol == cargo_symbol]
        cargo_inventory = cargo[0] if len(cargo) > 0 else None
        if not cargo_inventory:
            return LocalSpaceTradersRespose(
                f"Ship does not have any {cargo_symbol} to sell",
                0,
                0,
                "generic_behaviour.sell_cargo",
            )
        if not market:
            market = self.st.system_market(
                st.waypoints_view_one(ship.nav.waypoint_symbol)
            )
        if ship.nav.status != "DOCKED":
            st.ship_dock(ship)
        listing = market.get_tradegood(cargo_symbol)
        trade_volume = listing.trade_volume
        remaining_units = min(cargo_inventory.units, quantity)
        for i in range(0, math.ceil(cargo_inventory.units / trade_volume)):
            resp = st.ship_sell(
                ship, cargo_symbol, min(remaining_units, trade_volume, quantity)
            )
            remaining_units = remaining_units - trade_volume

            if not resp:
                pass
        self.log_market_changes(ship.nav.waypoint_symbol)
        return resp

    def sell_all_cargo(self, exceptions: list = [], market: Market = None):
        # needs reworked to use the sell_cargo
        ship = self.ship
        st = self.st
        listings = {}
        if not market:
            market = self.st.system_market(
                st.waypoints_view_one(ship.nav.waypoint_symbol)
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
            trade_volume = remaining_units = cargo.units
            if listing:
                trade_volume = listing.trade_volume

            for i in range(0, math.ceil(cargo.units / trade_volume)):
                resp = st.ship_sell(
                    ship, cargo.symbol, min(remaining_units, trade_volume)
                )
                remaining_units = remaining_units - trade_volume

                if not resp:
                    pass
                    # try the next cargo bit
        self.log_market_changes(ship.nav.waypoint_symbol)
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

    def get_neighbouring_extractors(self):
        return self.find_adjacent_ships(self.ship.nav.waypoint_symbol, ["EXCAVATOR"])

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
        results = try_execute_select(sql, (trade_symbol,), self.connection)
        return_obj = []
        for row in results or []:
            sys = System(row[2], row[3], row[4], row[5], row[6], [])
            price = row[0]
            waypoint_symbol = row[1]

            return_obj.append((waypoint_symbol, sys, price))
        return return_obj

    def purchase_what_you_can(self, cargo_symbol: str, quantity: int):
        # check the waypoint we're at has a market
        # check the market has the cargo symbol we're seeking
        # check the market_depth is sufficient, buy until quantity hit.

        return self.buy_cargo(cargo_symbol, quantity)

    def buy_cargo(self, cargo_symbol: str, quantity: int):
        # check current waypoint has a market that sells the tradegood
        # check we have enough cargo space
        # check we have enough credits

        if quantity < 0:
            raise ValueError("Quantity must be a positive integer or zero !")
        ship = self.ship
        current_waypoint = self.st.waypoints_view_one(ship.nav.waypoint_symbol)
        if "MARKETPLACE" not in [trait.symbol for trait in current_waypoint.traits]:
            return LocalSpaceTradersRespose(
                f"Waypoint {current_waypoint.symbol} is not a marketplace",
                0,
                0,
                "generic_behaviour.buy_cargo",
            )
        if ship.nav.status != "DOCKED":
            self.st.ship_dock(ship)

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
                break

        self.log_market_changes(current_waypoint.symbol)
        if not resp:
            if resp.error_code == 4217:
                ship = self.st.ships_view_one(ship.name, True)
            return resp
        return LocalSpaceTradersRespose(
            None, 0, None, "generic_behaviour.purchase_what_you_can"
        )

    def scan_local_system(self):
        st = self.st
        ship = self.ship
        current_system_sym = self.ship.nav.system_symbol

        # situation - when loading the waypoints, we get the systemWaypoint aggregate that doesn't have traits or other info.
        # QUESTION
        st.waypoints_view(current_system_sym, True)
        target_wayps = []
        if ship.seconds_until_cooldown < 60:
            wayps = st.ship_scan_waypoints(ship)
            if wayps:
                for wayp in wayps:
                    wayp: Waypoint
                    if "MARKETPLACE" in [t.symbol for t in wayp.traits]:
                        target_wayps.append(wayp)

        marketplaces = (
            st.find_waypoints_by_trait(current_system_sym, "MARKETPLACE") or []
        )

        shipyards = st.find_waypoints_by_trait(current_system_sym, "SHIPYARD") or []

        gate = st.find_waypoints_by_type_one(current_system_sym, "JUMP_GATE")
        uncharted_planets = st.find_waypoints_by_trait(
            ship.nav.system_symbol, "UNCHARTED"
        )
        if uncharted_planets:
            target_wayps.extend(
                p
                for p in uncharted_planets
                if p.type in ("PLANET", "MOON", "ORBITAL_STATION")
            )
        target_wayps.extend(marketplaces)
        target_wayps.extend(shipyards)
        target_wayps.append(gate)
        target_wayps = list(set(target_wayps))
        # remove dupes from target_wayps
        if not target_wayps or target_wayps[0] is None:
            return
        start = st.waypoints_view_one(ship.nav.waypoint_symbol)
        path = self.nearest_neighbour(target_wayps, start)

        for wayp_sym in path:
            waypoint = st.waypoints_view_one(wayp_sym)

            self.ship_intrasolar(wayp_sym)
            self.sleep_until_arrived()
            trait_symbols = [trait.symbol for trait in waypoint.traits]
            should_chart = False
            if "UNCHARTED" in trait_symbols:
                if len(trait_symbols) == 1:
                    self.sleep_until_ready()
                    wayps = st.ship_scan_waypoints(ship)
                    if wayps:
                        wayps = [w for w in wayps if w.symbol == waypoint.symbol]
                        waypoint = wayps[0]
                should_chart = True
            if "MARKETPLACE" in trait_symbols:
                market = st.system_market(waypoint, True)
                if market:
                    for listing in market.listings:
                        if listing.symbol in ("VALUABLES"):
                            should_chart = False
                        print(
                            f"item: {listing.symbol}, buy: {listing.purchase_price} sell: {listing.sell_price} - supply available {listing.supply}"
                        )
            if "SHIPYARD" in trait_symbols:
                shipyard = st.system_shipyard(waypoint, True)
                if shipyard:
                    for ship_type in shipyard.ship_types:
                        print(ship_type)
                        if ship_type in ("VALUABLES"):
                            should_chart = False
            if waypoint.type == "JUMP_GATE":
                jump_gate = st.system_jumpgate(waypoint, True)
                self.pathfinder._graph = self.pathfinder.load_jump_graph_from_db()
                self.pathfinder.save_graph()

    def ship_extrasolar_jump(self, dest_sys_sym: str, route: JumpGateRoute = None):
        if isinstance(dest_sys_sym, System):
            dest_sys = dest_sys_sym
            dest_sys_sym = self.st.find_waypoints_by_type_one(
                dest_sys_sym.symbol, "JUMP_GATE"
            )
        st = self.st
        ship = self.ship
        if ship.nav.system_symbol == dest_sys_sym:
            return True
        o_sys = st.systems_view_one(ship.nav.system_symbol)
        if not route:
            dest_sys = st.systems_view_one(dest_sys_sym)
            route = self.pathfinder.astar(o_sys, dest_sys, True)
        if not route:
            self.logger.error(f"Unable to jump to {o_sys.symbol} - no route found")
            return None
        else:
            dest_sys = route.end_system
        if ship.nav.system_symbol == dest_sys_sym:
            return True
        if ship.nav.status == "DOCKED":
            st.ship_orbit(ship)
        if ship.nav.travel_time_remaining > 0 or ship.seconds_until_cooldown > 0:
            self.sleep_until_ready()
        current_wp = st.waypoints_view_one(ship.nav.waypoint_symbol)
        self.st.logging_client.log_custom_event(
            "BEGIN_EXTRASOLAR_NAVIGATION",
            ship.name,
            {
                "origin_system": o_sys.symbol,
                "destination_system": dest_sys.symbol,
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
            next_sys
            sleep(ship.seconds_until_cooldown)
            resp = st.ship_jump(ship, next_sys.jump_gate_waypoint)
            if not resp:
                return resp
            if next_sys == dest_sys.symbol:
                # we've arrived, no need to sleepx
                break

        # Then, hit it.care
        return True

    def go_and_buy(
        self,
        target_tradegood: str,
        target_waypoint: "Waypoint",
        target_system: "System" = None,
        local_jumpgate: "Waypoint" = None,
        path: list = None,
        max_to_buy: int = None,
        burn_allowed=False,
    ) -> LocalSpaceTradersRespose:
        """Sends the ship to the target system and buys as much of the given target tradegood as possible.

        `local_jumpgate` is only necessary if you might be going extrasolar"""
        #
        # this needs to validate that we're going to make a profit with current prices.
        # if we're not, sleep for 15 minutes, and return false. By the time it picks up, either the market goods will have shuffled (hopefully) or there'll be a new contract assigned.
        #
        ship = self.ship
        st = self.st
        current_market = st.system_market(target_waypoint)

        if target_system and ship.nav.system_symbol != target_system.symbol:
            self.ship_intrasolar(local_jumpgate.symbol)
            self.ship_extrasolar_jump(target_waypoint.system_symbol, path)

        best_nav = None
        flight_mode = "CRUISE"
        if burn_allowed:
            current_wp = st.waypoints_view_one(ship.nav.waypoint_symbol)
            burn_nav = self.pathfinder.plot_system_nav(
                target_waypoint.system_symbol,
                current_wp,
                target_waypoint,
                ship.fuel_capacity / 2,
            )
            cruise_nav = self.pathfinder.plot_system_nav(
                target_waypoint.system_symbol,
                current_wp,
                target_waypoint,
                ship.fuel_capacity,
            )
            if (
                (burn_nav.seconds_to_destination) / 2
                < cruise_nav.seconds_to_destination
                and not burn_nav.needs_drifting
            ):
                best_nav = burn_nav
                flight_mode = "BURN"
            else:
                best_nav = cruise_nav

        self.ship_intrasolar(
            target_waypoint.symbol, flight_mode=flight_mode, route=best_nav
        )

        st.ship_dock(ship)
        if not current_market:
            self.logger.error(
                "No market found at waypoint %s", ship.nav.waypoint_symbol
            )
            self.st.sleep(SAFETY_PADDING)
            return current_market

        # empty anything that's not the goal.

        resp = self.purchase_what_you_can(
            target_tradegood, min(max_to_buy, ship.cargo_space_remaining)
        )
        if not resp:
            self.st.view_my_self(True)
            self.st.ships_view_one(ship.name, True)
            resp = self.purchase_what_you_can(
                target_tradegood, min(max_to_buy, ship.cargo_space_remaining)
            )
        if not resp:
            self.logger.error(
                "Couldn't purchase %s at %s, because %s",
                target_tradegood,
                ship.name,
                resp.error,
            )
            return resp
        return LocalSpaceTradersRespose(None, 0, None, url=f"{__name__}.fetch_half")

    def go_and_sell_or_fulfill(
        self,
        target_tradegood: str,
        target_waypoint: "Waypoint",
        target_system=None,
        burn_allowed=False,
    ):
        ship = self.ship
        if target_system:
            resp = self.ship_extrasolar_jump(target_system)
            if not resp:
                return False
        flight_mode = "CRUISE"
        best_nav = None
        if burn_allowed:
            current_wp = self.st.waypoints_view_one(ship.nav.waypoint_symbol)
            burn_nav = self.pathfinder.plot_system_nav(
                target_waypoint.system_symbol,
                current_wp,
                target_waypoint,
                ship.fuel_capacity / 2,
            )
            cruise_nav = self.pathfinder.plot_system_nav(
                target_waypoint.system_symbol,
                current_wp,
                target_waypoint,
                ship.fuel_capacity,
            )
            if (
                (burn_nav.seconds_to_destination) / 2
                < cruise_nav.seconds_to_destination
                and not burn_nav.needs_drifting
            ):
                best_nav = burn_nav
                flight_mode = "BURN"
            else:
                best_nav = cruise_nav

        resp = self.ship_intrasolar(
            target_waypoint, flight_mode=flight_mode, route=best_nav
        )
        if not resp and resp.error_code != 4204:
            return False
        # now that we're here, decide what to do. Options are:
        # transfer (skip for now, throw in a warning)
        # fulfill
        # sell
        self.st.ship_dock(self.ship)
        if "fulfil_wp" in self.behaviour_params:
            resp = self.fulfil_any_relevant()
        # elif "sell_wp" in self.behaviour_params:
        else:
            resp = self.sell_all_cargo()

        return resp

    def log_market_changes(self, market_s: str):
        wp = self.st.waypoints_view_one(market_s)
        pre_market = self.st.system_market(wp)
        post_market = self.st.system_market(wp, True)

        for t in pre_market.listings:
            changes = {}
            nt = post_market.get_tradegood(t.symbol)
            if not isinstance(nt, MarketTradeGoodListing):
                continue

            if nt.purchase_price != t.purchase_price:
                changes["purchase_price_change"] = nt.purchase_price - t.purchase_price
            if nt.sell_price != t.sell_price:
                changes["sell_price_change"] = nt.sell_price - t.sell_price
            if nt.supply != t.supply:
                changes["old_supply"] = t.supply
            if nt.activity != t.activity:
                changes["old_activity"] = t.activity
            if nt.trade_volume != t.trade_volume:
                changes["trade_volume_change"] = nt.trade_volume - t.trade_volume

            if len(changes) > 0:
                changes["purchase_price"] = nt.purchase_price
                changes["sell_price"] = nt.sell_price
                changes["supply"] = nt.supply
                changes["activity"] = nt.activity
                changes["trade_volume"] = nt.trade_volume
                changes["trade_symbol"] = t.symbol
                changes["market_symbol"] = market_s
                self.st.logging_client.log_custom_event(
                    "MARKET_CHANGES", self.ship.name, changes
                )

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

    def end(self, error: str = None):
        if "task_hash" in self.behaviour_params:
            sql = """update ship_tasks set completed = true where task_hash = %s"""
            try_execute_upsert(
                sql, (self.behaviour_params["task_hash"],), self.connection
            )
            self.st.sleep(20)
        self.st.release_connection()
        # self.st.db_client.connection.close()
        # self.st.logging_client.connection.close()

    def sleep_until_ready(self):
        if (
            self.ship.seconds_until_cooldown > 0
            or self.ship.nav.travel_time_remaining > 0
        ):
            self.st.release_connection()
            self.st.sleep(self.ship.seconds_until_cooldown + 1)

    def sleep_until_arrived(self):
        if self.ship.nav.travel_time_remaining > 0:
            self.st.release_connection()
            self.st.sleep(self.ship.nav.travel_time_remaining + 1)


if __name__ == "__main__":
    import sys

    sys.path.append(".")
    from dispatcherWK16 import lock_ship

    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "1"
    ship = f"{agent}-{ship_number}"
    bhvr = Behaviour(agent, ship, {})
    bhvr.ship = bhvr.st.ships_view_one(ship, True)
    bhvr.st.view_my_self(True)
    self = bhvr
    st = self.st
    ship = self.ship
