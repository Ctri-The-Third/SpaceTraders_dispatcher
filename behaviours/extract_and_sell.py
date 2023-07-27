import json
from spacetraders_v2 import SpaceTraders
from spacetraders_v2.ship import Ship
from spacetraders_v2.utils import sleep_until_ready
import threading
import logging
from time import sleep


class ExtractAndSell:
    def __init__(
        self,
        agent_name,
        ship_name,
        behaviour_params: dict = {},
        config_file_name="user.json",
    ) -> None:
        self.logger = logging.getLogger("bhvr_extract_and_sell")
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
        # all threads should have this.

        ship = self.ship
        st = self.st
        agent = self.agent
        if not ship.can_extract:
            return
        # move ship to a waypoint in its system with
        st.logging_client.log_beginning("EXTRACT_AND_SELL", ship.name, agent.credits)

        try:
            target_wp_sym = self.behaviour_params.get(
                "extract_waypoint",
                st.find_waypoint_by_type(
                    ship.nav.system_symbol, "ASTEROID_FIELD"
                ).symbol,
            )
            market_wp_sym = self.behaviour_params.get(
                "market_waypoint",
                st.find_waypoints_by_trait_one(
                    ship.nav.system_symbol, "MARKETPLACE"
                ).symbol,
            )
        except AttributeError as e:
            self.logger.error("could not find waypoints because %s", e)
            self.logger.info("Triggering waypoint cache refresh. Rerun behaviour.")
            st.waypoints_view(ship.nav.system_symbol, True)
            return

        self.ship_intrasolar(target_wp_sym)
        self.extract_till_full()
        self.ship_intrasolar(market_wp_sym)
        self.sell_all_cargo()
        self.refuel_if_low()
        st.logging_client.log_ending("EXTRACT_AND_SELL", ship.name, agent.credits)

    def ship_intrasolar(self, target_wp_symbol: "str"):
        if self.ship.nav.waypoint_symbol != target_wp_symbol:
            if self.ship.nav.status == "DOCKED":
                self.st.ship_orbit(self.ship)
            self.st.ship_move(self.ship, target_wp_symbol)
            sleep_until_ready(self.ship)

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
