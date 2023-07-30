import json
from straders_sdk import SpaceTraders
from time import sleep
from straders_sdk.ship import Ship
from straders_sdk.utils import set_logging


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
        self.behaviour_params = behaviour_params
        saved_data = json.load(open(config_file_name, "r+"))
        for agent in saved_data["agents"]:
            if agent["username"] == agent_name:
                token = agent["token"]
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
        )
        self.ship = self.st.ships_view_one(ship_name, force=False)
        self.agent = self.st.view_my_self()

    def run(self):
        pass

    def ship_intrasolar(self, target_wp_symbol: "str"):
        if self.ship.nav.waypoint_symbol != target_wp_symbol:
            if self.ship.nav.status == "DOCKED":
                self.st.ship_orbit(self.ship)
            resp = self.st.ship_move(self.ship, target_wp_symbol)
            if not resp:
                return False

            sleep_until_ready(self.ship)
            self.ship.nav.status = "IN_ORBIT"
            self.ship.nav.waypoint_symbol = target_wp_symbol
            return resp

    def extract_till_full(self):
        # need to validate that the ship's current WP is a valid location
        ship = self.ship
        st = self.st
        if ship.nav.status == "DOCKED":
            st.ship_orbit(ship)
        while ship.cargo_units_used < ship.cargo_capacity:
            resp = st.ship_extract(ship)
            if not resp:
                sleep(30)
                # ship is probably stuck in this state forever
            else:
                sleep_until_ready(self.ship)

    def refuel_if_low(self):
        ship = self.ship
        if ship.fuel_current < ship.fuel_capacity * 0.5:
            self.st.ship_refuel(ship)

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


def sleep_until_ready(ship: "Ship"):
    sleep(max(ship.seconds_until_cooldown, ship.nav.travel_time_remaining))
