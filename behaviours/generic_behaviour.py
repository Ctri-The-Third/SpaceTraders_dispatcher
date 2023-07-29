from spacetraders_v2 import SpaceTraders
from time import sleep
from spacetraders_v2.ship import Ship
from spacetraders_v2.utils import set_logging


class Behaviour:
    st: SpaceTraders
    ship: Ship

    def __init__(self, client: SpaceTraders, ship: Ship):
        self.st = client
        self.ship = ship
        set_logging()

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

    def sell_all_cargo(self):
        ship = self.ship
        st = self.st
        if ship.nav.status != "DOCKED":
            st.ship_dock(ship)
        for cargo in ship.cargo_inventory:
            st.ship_sell(ship, cargo.symbol, cargo.units)


def sleep_until_ready(ship: "Ship"):
    sleep(max(ship.seconds_until_cooldown, ship.nav.travel_time_remaining))
