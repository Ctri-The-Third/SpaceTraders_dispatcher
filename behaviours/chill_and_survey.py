import sys
import time

sys.path.append(".")

from behaviours.generic_behaviour import Behaviour
import logging
from straders_sdk.utils import try_execute_select, set_logging, waypoint_slicer
from straders_sdk.models import Waypoint, System

BEHAVIOUR_NAME = "CHILL_AND_SURVEY"
SAFETY_PADDING = 180


class ChillAndSurvey(Behaviour):
    """Expects a parameter blob containing 'asteroid_wp'"""

    def __init__(
        self,
        agent_name,
        ship_name,
        behaviour_params: dict = ...,
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
        self.target_wp_s = behaviour_params["asteroid_wp"]

    def default_params_obj(self):
        return_obj = super().default_params_obj()
        return_obj["asteroid_wp"] = "X1-TEST-AB12"

        return return_obj

    def run(self):
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
        st = self.st
        ship = self.ship
        agent = st.view_my_self()
        target_wp = st.waypoints_view_one(self.target_wp_s)
        if not target_wp:
            self.st.sleep(SAFETY_PADDING)
            self.end()
            return
        self.ship_extrasolar_jump(target_wp.system_symbol)
        self.ship_intrasolar(target_wp.symbol)
        self.sleep_until_ready()
        resp = st.ship_survey(ship)
        if not resp:
            self.st.sleep(SAFETY_PADDING)
            self.end()
            return
        self.end()


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "4"
    ship = f"{agent}-{ship_number}"
    behaviour_params = {"asteroid_wp": "X1-RV57-69965Z"}
    bhvr = ChillAndSurvey(agent, ship, behaviour_params or {})
    lock_ship(ship_number, "MANUAL", 60 * 24)
    bhvr.run()
    lock_ship(ship_number, "MANUAL", 0)
