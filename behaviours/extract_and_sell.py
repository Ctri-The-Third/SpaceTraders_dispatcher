import json
from spacetraders_v2 import SpaceTraders
from spacetraders_v2.ship import Ship
from spacetraders_v2.utils import set_logging
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
        self.logger = logging.getLogger("bhvr_extract_and_sell")
        self.logger.info("initialising...")

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
                "extract_waypoint",
                st.find_waypoint_by_type(
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

        self.ship_intrasolar(target_wp_sym)
        self.extract_till_full()
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
    set_logging()
    bhvr = ExtractAndSell("test", "test", {"extract_waypoint": "test"})
    bhvr.run()
