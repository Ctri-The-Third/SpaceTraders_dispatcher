import sys

sys.path.append(".")

import json
from straders_sdk import SpaceTraders
from straders_sdk.ship import Ship
from straders_sdk.utils import set_logging, waypoint_slicer
import logging
from behaviours.generic_behaviour import Behaviour
import time

BEHAVIOUR_NAME = "EXTRACT_AND_CHILL"


class ExtractAndChill(Behaviour):
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
        self.logger = logging.getLogger(BEHAVIOUR_NAME)
        self.cargo_to_target = self.behaviour_params.get("cargo_to_transfer", None)
        self.cargo_to_jettison = self.behaviour_params.get("cargo_to_jettison", [])

    def run(self):
        super().run()
        # all  threads should have this.

        starting_credts = self.agent.credits

        ship = self.ship
        self.st.ship_cooldown(ship)
        st = self.st
        agent = self.agent
        if not ship.can_extract:
            return
        # move ship to a waypoint in its system with

        st.logging_client.log_beginning("EXTRACT_AND_SELL", ship.name, agent.credits)
        if ship.cargo_space_remaining == 0:
            self.logger.info("Ship is full. resting.")
            time.sleep(60)
        try:
            target_wp_sym = self.behaviour_params.get("asteroid_wp", None)
            if not target_wp_sym:
                target_wp = st.find_waypoints_by_type_one(
                    ship.nav.system_symbol, "ASTEROID"
                )

                target_wp_sym = target_wp.symbol
            else:
                target_wp = st.waypoints_view_one(ship.nav.system_symbol, target_wp_sym)

        except AttributeError as e:
            self.logger.error("could not find waypoints because %s", e)
            self.logger.info("Triggering waypoint cache refresh. Rerun behaviour.")
            st.waypoints_view(ship.nav.system_symbol, True)
            return

        # in a circumstance where the ship isn't in the specified system, it will go.
        self.ship_extrasolar(st.systems_view_one(waypoint_slicer(target_wp_sym)))
        self.ship_intrasolar(target_wp_sym)
        self.sleep_until_ready()
        if (
            ship.can_survey and target_wp.type == "ASTEROID"
        ):  # this isn't appropriate for siphoning.
            st.ship_survey(ship)

        self.extract_till_full(self.cargo_to_target, self.cargo_to_jettison)
        if ship.can_siphon > 0 and target_wp.type == "GAS_GIANT":
            self.siphon_till_full()

        ship_cargo_symbols = [cargo.symbol for cargo in ship.cargo_inventory]
        for jettison_target in self.cargo_to_jettison:
            if jettison_target in ship_cargo_symbols:
                match = [
                    cargo
                    for cargo in ship.cargo_inventory
                    if cargo.symbol == jettison_target
                ]
                if match:
                    st.ship_jettison_cargo(ship, match[0].symbol, match[0].units)
        self.end()
        st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
        self.logger.info(
            "Completed. Credits: %s, change = %s",
            agent.credits,
            agent.credits - starting_credts,
        )

        # go through each option, determine CPH and pick the best one.
        # Throw in a 1 minute offset   so that selling at distance 0 isn't always best.


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "1E"
    ship = f"{agent}-{ship_number}"
    set_logging(logging.DEBUG)
    behaviour_params = {
        "asteroid_wp": "X1-U49-FA4A",
        "cargo_to_transfer": ["*"],
        "cargo_to_jettison": [
            "QUARTZ_SAND",
            "ICE_WATER",
            "SILICON_CRYSTALS",
        ],
    }
    bhvr = ExtractAndChill(agent, ship, behaviour_params)
    lock_ship(ship, "MANUAL", bhvr.connection, duration=120)
    set_logging(logging.DEBUG)
    bhvr.run()
    lock_ship(ship, "", bhvr.connection, duration=0)
