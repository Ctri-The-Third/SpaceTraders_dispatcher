import sys

sys.path.append(".")
from behaviours.generic_behaviour import Behaviour
import logging
from straders_sdk.utils import try_execute_select, set_logging, waypoint_slicer
import time

BEHAVIOUR_NAME = "MONITOR_CHEAPEST_SHIPYARD_PRICE"


class MonitorPrices(Behaviour):
    """Expects a parameter blob containing 'ship_type'"""

    def __init__(
        self,
        agent_name,
        ship_name,
        behaviour_params: dict = ...,
        config_file_name="user.json",
        session=None,
    ) -> None:
        self.graph = None
        super().__init__(
            agent_name, ship_name, behaviour_params, config_file_name, session
        )

    def run(self):
        super().run()
        ship = self.ship
        st = self.st
        agent = st.view_my_self()
        # check all markets in the system
        st.logging_client.log_beginning(BEHAVIOUR_NAME, ship.name, agent.credits)

        time.sleep(max(ship.seconds_until_cooldown, ship.nav.travel_time_remaining))

        sql = """select ship_type, cheapest_location from shipyard_prices
            where ship_type = %s"""
        rows = try_execute_select(
            self.connection, sql, (self.behaviour_params["ship_type"],)
        )
        if not rows:
            self.logger.error(
                "Couldn't find ship type %s", self.behaviour_params["ship_type"]
            )
            time.sleep(600)
            return
        print(f"Searching for ship {rows[0][0]} at  wayp {rows[0][1]} ")
        target_wp = rows[0][1]
        target_sys_sym = waypoint_slicer(target_wp)
        target_sys = st.systems_view_one(target_sys_sym)
        self.ship_extrasolar(target_sys)
        self.ship_intrasolar(target_wp)

        wp = st.waypoints_view_one(target_sys_sym, target_wp)
        if wp.has_shipyard:
            st.system_shipyard(wp, True)
            time.sleep(600)


if __name__ == "__main__":
    set_logging(level=logging.DEBUG)
    agent_symbol = "CTRI-UWK5-"
    ship_suffix = "25"
    params = None
    params = {"ship_type": "SHIP_ORE_HOUND"}
    MonitorPrices(agent_symbol, f"{agent_symbol}-{ship_suffix}", params).run()
