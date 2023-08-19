import sys

sys.path.append(".")

import json
from straders_sdk import SpaceTraders
from straders_sdk.ship import Ship
from straders_sdk.utils import set_logging, waypoint_slicer
import logging
from behaviours.generic_behaviour import Behaviour


class ExtractAndSell(Behaviour):
    def __init__(
        self,
        agent_name,
        ship_name,
        behaviour_params: dict = {},
        config_file_name="user.json",
    ) -> None:
        super().__init__(agent_name, ship_name, behaviour_params, config_file_name)

        self.logger = logging.getLogger("bhvr_extract_and_sell")

    def run(self):
        super().run()
        # all  threads should have this.
        self.logger.info("Beginning...")
        starting_credts = self.agent.credits
        ship = self.ship
        st = self.st
        agent = self.agent
        if not ship.can_extract:
            return
        # move ship to a waypoint in its system with
        st.logging_client.log_beginning("EXTRACT_AND_SELL", ship.name, agent.credits)

        try:
            target_wp_sym = self.behaviour_params.get(
                "asteroid_wp",
                st.find_waypoints_by_type_one(
                    ship.nav.system_symbol, "ASTEROID_FIELD"
                ).symbol,
            )
            market_wp_sym = self.behaviour_params.get(
                "market_waypoint",
                target_wp_sym,
            )
        except AttributeError as e:
            self.logger.error("could not find waypoints because %s", e)
            self.logger.info("Triggering waypoint cache refresh. Rerun behaviour.")
            st.waypoints_view(ship.nav.system_symbol, True)
            return

        # in a circumstance where the ship isn't in the specified system, it will go.
        self.ship_extrasolar(waypoint_slicer(target_wp_sym))
        self.ship_intrasolar(target_wp_sym)
        self.extract_till_full([])
        self.ship_intrasolar(market_wp_sym)
        self.sell_all_cargo()
        self.refuel_if_low()
        st.logging_client.log_ending("EXTRACT_AND_SELL", ship.name, agent.credits)
        self.logger.info(
            "Completed. Credits: %s, change = %s",
            agent.credits,
            agent.credits - starting_credts,
        )


if __name__ == "__main__":
    agent = sys.argv[1] if len(sys.argv) >= 3 else "CTRI"
    ship = sys.argv[2] if len(sys.argv) >= 3 else "CTRI-3"
    set_logging()
    bhvr = ExtractAndSell(agent, ship)
    bhvr.run()
