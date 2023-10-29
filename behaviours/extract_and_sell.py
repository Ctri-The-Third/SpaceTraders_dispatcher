import sys

sys.path.append(".")

import json
from straders_sdk import SpaceTraders
from straders_sdk.ship import Ship
from straders_sdk.utils import set_logging, waypoint_slicer
import logging
from behaviours.generic_behaviour import Behaviour
import time


class ExtractAndSell(Behaviour):
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

    def run(self):
        super().run()
        # all  threads should have this.
        self.logger.info("Beginning...")
        starting_credts = self.agent.credits

        # this behaviour involves inventory, which isn't stashed in the SDK yet
        ship = self.ship = self.st.ships_view_one(self.ship.name, True)
        st = self.st
        agent = self.agent
        if not ship.can_extract:
            return
        # move ship to a waypoint in its system with
        st.logging_client.log_beginning("EXTRACT_AND_SELL", ship.name, agent.credits)

        try:
            target_wp_sym = self.behaviour_params.get("asteroid_wp", None)
            if not target_wp_sym:
                target_wp = st.find_waypoints_by_type_one(
                    ship.nav.system_symbol, "ASTEROID"
                )

                target_wp_sym = target_wp.symbol

            market_wp_sym = self.behaviour_params.get(
                "market_waypoint",
                None,
            )

            if not market_wp_sym:
                # find a market that buys all the cargo we're selling
                market_wp_syms = []
                for tradegood in ship.cargo_inventory:
                    goods = self.find_best_market_systems_to_sell(tradegood.symbol)

        except AttributeError as e:
            self.logger.error("could not find waypoints because %s", e)
            self.logger.info("Triggering waypoint cache refresh. Rerun behaviour.")
            st.waypoints_view(ship.nav.system_symbol, True)
            return

        current_wp = st.waypoints_view_one(
            ship.nav.system_symbol, ship.nav.waypoint_symbol
        )
        # in a circumstance where the ship isn't in the specified system, it will go.

        self.ship_extrasolar(st.systems_view_one(waypoint_slicer(target_wp_sym)))
        self.ship_intrasolar(target_wp_sym)
        time.sleep(ship.seconds_until_cooldown)
        if ship.can_survey:
            st.ship_survey(ship)

        cutoff_cargo_limit = None
        if ship.extract_strength > 0:
            cutoff_cargo_limit = ship.cargo_capacity - ship.extract_strength / 2
        self.extract_till_full([], cutoff_cargo_limit)
        self.ship_intrasolar(market_wp_sym)
        self.sell_all_cargo()
        st.system_market(current_wp, True)

        self.end()
        st.logging_client.log_ending("EXTRACT_AND_SELL", ship.name, agent.credits)
        self.logger.info(
            "Completed. Credits: %s, change = %s",
            agent.credits,
            agent.credits - starting_credts,
        )


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "1"
    ship = f"{agent}-{ship_number}"
    set_logging(logging.DEBUG)
    behaviour_params = {}  # {"asteroid_wp": "X1-QB20-13975F"}
    bhvr = ExtractAndSell(agent, ship, behaviour_params)
    lock_ship(ship, "MANUAL", bhvr.connection, duration=120)
    set_logging(logging.DEBUG)
    bhvr.run()
    lock_ship(ship, "", bhvr.connection, duration=0)
