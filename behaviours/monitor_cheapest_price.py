import sys

sys.path.append(".")
from behaviours.generic_behaviour import Behaviour
import logging
from straders_sdk.utils import try_execute_select, set_logging, waypoint_slicer
from straders_sdk.models import Waypoint, System
import time, math, threading

BEHAVIOUR_NAME = "MONITOR_CHEAPEST_SHIPYARD_PRICE"
SAFETY_PADDING = 180


class MonitorCheapestShipyard(Behaviour):
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
        scan_thread = threading.Thread(
            target=self.scan_waypoints, daemon=False, name="scan_thread"
        )
        # scan_thread.start()
        starting_system = st.systems_view_one(ship.nav.system_symbol)
        st.logging_client.log_beginning(
            BEHAVIOUR_NAME,
            ship.name,
            agent.credits,
            behaviour_params=self.behaviour_params,
        )

        self.sleep_until_ready()

        sql = """select st.*, s.system_symbol, s.x, s.y from shipyard_types st
        join waypoints w on st.shipyard_symbol = w.waypoint_symbol
        join systems s on w.system_symbol = s.system_symbol
        where ship_type = %s
        and ship_cost is not null
        order by ship_cost asc """
        rows = try_execute_select(
            self.connection, sql, (self.behaviour_params["ship_type"],)
        )
        if not rows:
            self.logger.error(
                "Couldn't find ship type %s", self.behaviour_params["ship_type"]
            )
            self.st.sleep(180)
            return
        route = None
        for row in rows:
            destination_system = System(row[4], "", "", row[5], row[6], [])
            new_route = self.pathfinder.astar(starting_system, destination_system)

            if new_route:
                route = new_route
                break
        if not route:
            print(f"Couldn't find a route to any shipyards that sell {rows[0][1]}!")
            self.st.sleep(SAFETY_PADDING)
            return
        else:
            # print(
            #    f"Searching for ship {rows[0][1]} at system {route.end_system.symbol}"
            # )
            pass

        target_wp = row[0]
        target_sys_sym = waypoint_slicer(target_wp)
        target_sys = st.systems_view_one(target_sys_sym)
        self.sleep_until_ready()
        self.ship_extrasolar_jump(target_sys.symbol)
        resp = self.ship_intrasolar(target_wp)
        if not resp:
            self.st.sleep(SAFETY_PADDING)
            self.end()
            self.st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
        wp = st.waypoints_view_one(target_wp)
        if wp.has_shipyard:
            st.system_shipyard(wp, True)
            self.end()

            self.st.sleep(SAFETY_PADDING)
        if scan_thread.is_alive():
            scan_thread.join()
        self.st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    # 3, 4,5,6,7,8,9
    # A is the surveyor
    ship_suffix = sys.argv[2] if len(sys.argv) > 2 else "8"
    ship = f"{agent}-{ship_suffix}"
    params = {"ship_type": "SHIP_SIPHON_DRONE"}
    bhvr = MonitorCheapestShipyard(agent, f"{ship}", params)
    lock_ship(ship, "MANUAL", duration=120)
    set_logging(logging.DEBUG)
    bhvr.run()
    lock_ship(ship, "", duration=0)
