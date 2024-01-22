import sys

sys.path.append(".")

import json
from straders_sdk import SpaceTraders
from straders_sdk.ship import Ship
from straders_sdk.utils import set_logging, waypoint_slicer
import logging
from behaviours.generic_behaviour import Behaviour
import time
import math

BEHAVIOUR_NAME = "EXTRACT_AND_GO_SELL"
SAFETY_PADDING = 180


class ExtractAndGoSell(Behaviour):
    def __init__(
        self,
        agent_name,
        ship_name,
        behaviour_params: dict = {},
        config_file_name="user.json",
        session=None,
        connection=None,
    ) -> None:
        super().__init__(
            agent_name,
            ship_name,
            behaviour_params,
            config_file_name,
            session,
            connection,
        )
        self
        self.logger = logging.getLogger("bhvr_extract_and_sell")

    def default_params_obj(self):
        return_obj = super().default_params_obj()
        return_obj["asteroid_wp"] = "X1-PK16-AB12"
        return_obj["cargo_to_transfer"] = ["*"]
        return_obj["fulfil_wp"] = "X1-TEST-F99"

        return return_obj

    def run(self):
        super().run()
        self.ship = self.st.ships_view_one(self.ship_name)
        self.sleep_until_ready()
        self.st.logging_client.log_beginning(
            BEHAVIOUR_NAME,
            self.ship.name,
            self.agent.credits,
            behaviour_params=self.behaviour_params,
        )

        self._run()
        self.end()

    def _run(self):
        # all  threads should have this.

        starting_credts = self.agent.credits

        # this behaviour involves inventory, which isn't stashed in the SDK yet
        ship = self.ship  # = self.st.ships_view_one(self.ship.name, True)
        self.st.ship_cooldown(ship)
        st = self.st
        agent = self.agent
        if not ship.can_extract and not ship.can_siphon:
            return
        # move ship to a waypoint in its system with
        st.logging_client.log_beginning(
            BEHAVIOUR_NAME,
            ship.name,
            agent.credits,
            behaviour_params=self.behaviour_params,
        )

        try:
            target_wp_sym = self.behaviour_params.get("asteroid_wp", None)
            if not target_wp_sym:
                target_wp = st.find_waypoints_by_type_one(
                    ship.nav.system_symbol, "ASTEROID"
                )

                target_wp_sym = target_wp.symbol
            else:
                target_wp = st.waypoints_view_one(target_wp_sym)
            market_wp_sym = self.behaviour_params.get(
                "market_wp",
                None,
            )

        except AttributeError as e:
            self.logger.error("could not find waypoints because %s", e)
            self.logger.info("Triggering waypoint cache refresh. Rerun behaviour.")
            st.waypoints_view(ship.nav.system_symbol, True)
            return

        current_wp = st.waypoints_view_one(ship.nav.waypoint_symbol)

        # in a circumstance where the ship isn't in the specified system, it will go.
        self.ship_extrasolar_jump(waypoint_slicer(target_wp_sym))
        self.ship_intrasolar(target_wp_sym)
        #
        # if we have any fuel in the inventory, refuel.
        #
        self.maybe_refuel_from_cargo()
        if ship.can_survey and target_wp.type in (
            "ASTEROID",
            "ENGINEERED_ASTEROID",
        ):  # this isn't appropriate for siphoning.
            st.ship_survey(ship)

        cutoff_cargo_limit = None
        if ship.extract_strength > 0 and target_wp.type in (
            "ASTEROID",
            "ENGINEERED_ASTEROID",
        ):
            cutoff_cargo_limit = ship.cargo_capacity - ship.extract_strength / 2

            self.extract_till_full([], [], cutoff_cargo_limit)
        if ship.can_siphon > 0 and target_wp.type == "GAS_GIANT":
            self.siphon_till_full(cutoff_cargo_limit)

        if not market_wp_sym:
            market_wp_sym = self.get_market_and_jettison_waste(
                ship, st, current_wp.symbol
            )
        if market_wp_sym:
            for cargo in ship.cargo_inventory:
                self.go_and_sell_or_fulfill(cargo.symbol, market_wp_sym)

            market_wp = st.waypoints_view_one(market_wp_sym)

            distance_to_market = self.pathfinder.calc_distance_between(
                market_wp, target_wp
            )

            fuel_capacity = ship.fuel_capacity
            fuel_capacity = 80

            if distance_to_market > fuel_capacity / 2:
                self.buy_cargo("FUEL", math.ceil(((distance_to_market / 2) / 100)))
            # CHECK DISTANCE BACK TO ASTEROID. If it's more than half our fuel capacity, buy one fuel.

        self.end()
        st.logging_client.log_ending("EXTRACT_AND_SELL", ship.name, agent.credits)
        self.logger.info(
            "Completed. Credits: %s, change = %s",
            agent.credits,
            agent.credits - starting_credts,
        )

    def maybe_refuel_from_cargo(self):
        ship = self.ship
        st = self.st
        # fuel missing = fuel capacity - fuel level
        fuel_missing = math.ceil((ship.fuel_capacity - ship.fuel_current) / 100)
        if fuel_missing > 0:
            for cargo in ship.cargo_inventory:
                if cargo.symbol == "FUEL":
                    st.ship_dock(ship)
                    st.ship_refuel(ship, True)

    def get_market_and_jettison_waste(
        self, ship: Ship, client: SpaceTraders, starting_wp_s: str
    ) -> str:
        market_wp_sym = None
        best_tradegood_option = [None, None]
        # find a market that buys all the cargo we're selling
        starting_wp = client.waypoints_view_one(starting_wp_s)
        best_total_cph = 0
        start_system = client.systems_view_one(
            waypoint_slicer(starting_wp_s), starting_wp_s
        )

        for tradegood in ship.cargo_inventory:
            # start simple, find the best market for each good, in terms of CPH

            options = self.find_best_market_systems_to_sell(tradegood.symbol)
            if len(options) == 0:
                client.ship_jettison_cargo(ship, tradegood.symbol, tradegood.units)
            best_tradegood_option = [None, None]
            best_tradegood_cph = 0
            for option in options:
                end_system = option[1]
                end_wp = self.st.waypoints_view_one(option[0])
                market = self.st.system_market(end_wp)

                # never sell to exporting markets.
                tg = market.get_tradegood(tradegood.symbol)
                if tg and tg.type not in (
                    "EXCHANGE",
                    "IMPORT",
                ):
                    continue

                distance_to_market = self.pathfinder.calc_distance_between(
                    start_system, end_system
                )
                time_to_target = self.pathfinder.calc_travel_time_between_wps(
                    start_system, end_system, ship.engine.speed
                )
                if distance_to_market == 0:
                    distance_to_market = self.pathfinder.calc_distance_between(
                        starting_wp, end_wp
                    )
                    time_to_target = self.pathfinder.calc_travel_time_between_wps(
                        starting_wp, end_wp, ship.engine.speed
                    )

                cph = (option[2] * tradegood.units) / (time_to_target + 60)
                if cph > best_tradegood_cph:
                    if start_system != end_system:
                        # check we can go there
                        route = self.pathfinder.astar(start_system, end_system)
                        if not route:
                            continue
                    best_tradegood_option = option
                    best_tradegood_cph = cph
            if best_tradegood_cph > best_total_cph:
                best_total_cph = best_tradegood_cph
                market_wp_sym = best_tradegood_option[0]
        return market_wp_sym
        # go through each option, determine CPH and pick the best one.
        # Throw in a 1 minute offset   so that selling at distance 0 isn't always best.


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "1"
    ship = f"{agent}-{ship_number}"
    set_logging(logging.DEBUG)
    behaviour_params = {
        "asteroid_wp": "X1-PK16-B40",
        "script_name": "EXTRACT_AND_SELL",
        "cargo_to_transfer": ["*"],
    }
    bhvr = ExtractAndGoSell(agent, ship, behaviour_params)
    lock_ship(ship, "MANUAL", duration=60 * 24)
    set_logging(logging.DEBUG)
    bhvr.run()
    lock_ship(ship, "", duration=0)
