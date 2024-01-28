import sys

sys.path.append(".")
from behaviours.generic_behaviour import Behaviour
import logging
from straders_sdk.utils import try_execute_select, set_logging, waypoint_slicer
from straders_sdk.models import Waypoint, System
import time, math, threading
from datetime import datetime, timedelta

BEHAVIOUR_NAME = "MONITOR_SPECIFIC_WAYPOINT"
SAFETY_PADDING = 180


class MonitorPrices(Behaviour):
    """Expects a parameter blob containing a waypoint symbol `waypoint`

    required: waypoint - sets the location the ship will travel.
    Note, also visits neighbouring orbitals.
    Performs the ping after every quarter of an hour, or on arrival."""

    def __init__(
        self,
        agent_name,
        ship_name,
        behaviour_params: dict = ...,
        config_file_name="user.json",
        session=None,
    ) -> None:
        super().__init__(
            agent_name,
            ship_name,
            behaviour_params,
            config_file_name,
            session,
        )
        self

    def default_params_obj(self):
        return_obj = super().default_params_obj()
        return_obj["waypoint"] = "X1-TN14-A2"

        return return_obj

    def run(self):
        super().run()
        self.st.logging_client.log_beginning(
            BEHAVIOUR_NAME,
            self.ship.name,
            self.agent.credits,
            behaviour_params=self.behaviour_params,
        )
        self.sleep_until_ready()

        self._run()
        self.end()

    def _run(self):
        ship = self.ship
        st = self.st
        destination = self.behaviour_params.get("waypoint", None)
        if not destination:
            logging.error("No destination specified")
            self.end()
            self.st.logging_client.log_ending(
                BEHAVIOUR_NAME, ship.name, self.agent.credits
            )
            time.sleep(SAFETY_PADDING)
            return
        waypoint = st.waypoints_view_one(destination)
        waypoint: Waypoint

        self.ship_intrasolar(waypoint.symbol)

        market = st.system_market(waypoint)

        if market.is_stale(60 * 15) or (datetime.now().minute % 15) == 0:
            coorbitals = st.find_waypoints_by_coords(
                waypoint.system_symbol, waypoint.x, waypoint.y
            )

            coorbitals.remove(waypoint)
            for coorbital in coorbitals:
                coorbital: Waypoint
                self.ship_intrasolar(coorbital.symbol)
                if coorbital.has_market:
                    self.log_market_changes(coorbital.symbol)
                if coorbital.has_shipyard:
                    self.st.system_shipyard(coorbital, True)
        self.ship_intrasolar(waypoint.symbol)
        if waypoint.has_market:
            self.log_market_changes(waypoint.symbol)
        if waypoint.has_shipyard:
            self.st.system_shipyard(waypoint, True)
        self.st.sleep(SAFETY_PADDING)
        st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, self.agent.credits)
        self.end()

    def monitor_market(self, waypoint_symbol):
        st = self.st
        waypoint = st.waypoints_view_one(waypoint_symbol)
        waypoint: Waypoint
        if waypoint.has_market:
            self.log_market_changes(waypoint.symbol)
        if waypoint.has_shipyard:
            self.st.system_shipyard(waypoint, True)


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    # 3, 4,5,6,7,8,9
    # A is the surveyor
    ship_suffix = sys.argv[2] if len(sys.argv) > 2 else "2"
    ship = f"{agent}-{ship_suffix}"
    params = {"waypoint": "X1-TN14-A2"}
    bhvr = MonitorPrices(agent, f"{ship}", params)
    lock_ship(ship, "MANUAL", duration=120)
    set_logging(logging.DEBUG)
    bhvr.run()
    lock_ship(ship, "", duration=0)
