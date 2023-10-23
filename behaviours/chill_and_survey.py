import sys

sys.path.append(".")
from behaviours.generic_behaviour import Behaviour
import logging
from straders_sdk.utils import try_execute_select, set_logging, waypoint_slicer
from straders_sdk.models import Waypoint, System
import time, math, threading

BEHAVIOUR_NAME = "CHILL_AND_SURVEY"
SAFETY_PADDING = 60


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
        st = self.st
        ship = self.ship
        self.target_wp_s = behaviour_params["asteroid_wp"]
        target_sys = st.systems_view_one(waypoint_slicer(self.target_wp_s))
        target_wp = st.waypoints_view_one(
            waypoint_slicer(self.target_wp_s), self.target_wp_s
        )
        if not target_wp:
            time.sleep(SAFETY_PADDING)
            self.end()
            return
        self.ship_extrasolar(target_sys)
        self.ship_intrasolar(target_wp.symbol)
        self.sleep_until_ready()
        resp = st.ship_survey(ship.name)
        if not resp:
            time.sleep(SAFETY_PADDING)
            self.end()
            return
        self.end()
