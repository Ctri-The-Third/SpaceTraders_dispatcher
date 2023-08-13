import json
from straders_sdk import SpaceTraders
from time import sleep
from straders_sdk.ship import Ship
from straders_sdk.models import Waypoint
from straders_sdk.utils import set_logging
import logging
import math


class Behaviour:
    st: SpaceTraders
    ship: Ship

    def __init__(
        self,
        agent_name,
        ship_name,
        behaviour_params: dict = {},
        config_file_name="user.json",
    ) -> None:
        set_logging()
        self.logger = logging.getLogger(__name__)
        self.behaviour_params = behaviour_params or {}
        saved_data = json.load(open(config_file_name, "r+"))
        token = None
        for agent in saved_data["agents"]:
            if agent["username"] == agent_name:
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
        )
        self.connection = self.st.db_client.connection
        self.ship = self.st.ships_view_one(ship_name, force=True)
        self.st.ship_cooldown(self.ship)
        # get the cooldown info as well from the DB
        self.agent = self.st.view_my_self()

    def run(self):
        pass

    def ship_intrasolar(self, target_wp_symbol: "str", sleep_till_done=True):
        st = self.st
        ship = self.ship
        wp = self.st.waypoints_view_one(ship.nav.system_symbol, target_wp_symbol)

        fuel_cost = self.determine_fuel_cost(self.ship, wp)
        if fuel_cost > ship.fuel_current and ship.fuel_capacity > 0:
            # need to refuel (note that satelites don't have a fuel tank, and don't need to refuel.)
            self.refuel_if_low()
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
            self.logger.debug(
                "moved to %s, time to destination %s",
                ship.name,
                ship.nav.travel_time_remaining,
            )
            return resp

    def extract_till_full(self, cargo_to_target: list = None):
        # need to validate that the ship'  s current WP is a valid location
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

            resp = st.ship_extract(ship, survey)
            if not resp:
                sleep(30)
                return
                # ship is probably stuck in this state forever
            else:
                sleep_until_ready(self.ship)

    def refuel_if_low(self):
        ship = self.ship
        if ship.fuel_capacity == 0:
            return
        refuel_points = self.st.find_waypoints_by_trait(
            self.ship.nav.system_symbol, "MARKETPLACE"
        )
        nearest_refuel_wp = None
        nearest_refuel_distance = 99999
        for refuel_point in refuel_points:
            distance = self.distance_from_ship(ship, refuel_point)
            if distance < nearest_refuel_distance:
                nearest_refuel_distance = distance
                nearest_refuel_wp = refuel_point
        if nearest_refuel_wp is not None:
            previous_state = None
            if self.determine_fuel_cost(ship, nearest_refuel_wp) > ship.fuel_current:
                previous_state = ship.nav.flight_mode
                self.st.ship_patch_nav(ship, "DRIFT")
            self.ship_intrasolar(nearest_refuel_wp.symbol)
            self.st.ship_dock(ship)
            self.st.ship_refuel(ship)
            if previous_state:
                self.st.ship_patch_nav(ship, previous_state)

    def sell_all_cargo(self, exceptions: list = []):
        ship = self.ship
        st = self.st
        if ship.nav.status != "DOCKED":
            st.ship_dock(ship)
        for cargo in ship.cargo_inventory:
            if cargo.symbol in exceptions:
                continue
            st.ship_sell(ship, cargo.symbol, cargo.units)

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


def sleep_until_ready(ship: "Ship"):
    sleep(max(ship.seconds_until_cooldown, ship.nav.travel_time_remaining))


def distance_between_wps(source: Waypoint, target_wp: Waypoint) -> float:
    return math.sqrt((target_wp.x - source.x) ** 2 + (target_wp.y - source.y) ** 2)
