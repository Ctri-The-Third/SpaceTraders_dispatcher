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
            self.end()

            time.sleep(600)
        self.st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)


if __name__ == "__main__":
    from dispatcherWK12 import lock_ship

    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    # 3, 4,5,6,7,8,9
    # A is the surveyor
    ship_suffix = sys.argv[2] if len(sys.argv) > 2 else "2"
    ship = f"{agent}-{ship_suffix}"
    params = {"ship_type": "SHIP_ORE_HOUND"}
    bhvr = MonitorPrices(agent, f"{ship}", params)
    lock_ship(ship, "MANUAL", bhvr.connection, duration=120)
    set_logging(logging.DEBUG)
    bhvr.run()
    lock_ship(ship, "", bhvr.connection, duration=0)
