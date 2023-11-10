import sys

sys.path.append(".")
from behaviours.generic_behaviour import Behaviour
import logging
from straders_sdk.utils import try_execute_select, set_logging, waypoint_slicer
from straders_sdk.models import Waypoint, System
import time, math, threading

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
        scan_thread = threading.Thread(
            target=self.scan_waypoints, daemon=False, name="scan_thread"
        )
        # scan_thread.start()
        starting_system = st.systems_view_one(ship.nav.system_symbol)
        st.logging_client.log_beginning(BEHAVIOUR_NAME, ship.name, agent.credits)

        time.sleep(max(ship.seconds_until_cooldown, ship.nav.travel_time_remaining))

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
            time.sleep(30)
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
            time.sleep(60)
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
        self.ship_extrasolar(target_sys)
        resp = self.ship_intrasolar(target_wp)
        if not resp:
            time.sleep(60)
            self.end()
            self.st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
        wp = st.waypoints_view_one(target_sys_sym, target_wp)
        if wp.has_shipyard:
            st.system_shipyard(wp, True)
            self.end()

            time.sleep(60)
        if scan_thread.is_alive():
            scan_thread.join()
        self.st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)

    def scan_waypoints(self):
        st = self.st
        ship = self.ship
        #
        # get 20 unscanned waypoints, focusing on stations, asteroids, and gates
        #
        wayps = (
            self.get_twenty_unscanned_waypoints("ORBITAL_STATION")
            or self.get_twenty_unscanned_waypoints("ASTEROID_FIELD")
            or self.get_twenty_unscanned_waypoints("JUMP_GATE")
            or []
        )

        for wayp in wayps:
            resp = st.waypoints_view_one(wayp[2], wayp[0], True)
            time.sleep(1.2)
            if ship.seconds_until_cooldown > 0:
                continue
            if ship.nav.travel_time_remaining > 0:
                continue
            if ship.can_survey:
                st.ship_survey(ship)
                time.sleep(0.5)

        #
        # get 20 unscanned jump gates
        #

        rows = self.get_twenty_unscanned_jumpgates()

        for row in rows:
            jump_gate_sym = row[0]
            sys = waypoint_slicer(jump_gate_sym)

            wp = st.waypoints_view_one(sys, jump_gate_sym)
            if not wp.is_charted:
                wp = st.waypoints_view_one(sys, jump_gate_sym, True)
            if not wp.is_charted:
                time.sleep(1.2)

                continue
            resp = st.system_jumpgate(wp, True)
            time.sleep(1.2)
            if ship.seconds_until_cooldown > 0:
                continue
            if ship.nav.travel_time_remaining > 0:
                continue
            if ship.can_survey:
                st.ship_survey(ship)
                time.sleep(0.5)

        #
        # MARKETS and SHIPYARDS
        #

        rows = self.get_twenty_unscanned_markets_or_shipyards()
        for row in rows:
            wp_sym = row[0]
            sys = waypoint_slicer(wp_sym)
            wp = st.waypoints_view_one(sys, wp_sym)
            if wp.has_market:
                resp = st.system_market(wp, True)
                time.sleep(1.2)
            if wp.has_shipyard:
                resp = st.system_shipyard(wp, True)
                time.sleep(1.2)

    def get_twenty_unscanned_waypoints(self, type: str = r"%s") -> list[str]:
        sql = """
        select * from waypoints_not_scanned
        where type = %s
        order by random() 
        limit 20
        """
        return try_execute_select(self.st.db_client.connection, sql, (type,))

    def get_twenty_unscanned_jumpgates(self) -> list[str]:
        sql = """ select * from jumpgates_scanned
where charted and not scanned
order by random()
limit 20"""
        return try_execute_select(self.st.db_client.connection, sql, ())

    def get_twenty_unscanned_markets_or_shipyards(self) -> list[str]:
        sql = """select * from mkt_shpyrds_waypoints_scanned
where not scanned
order by random()"""
        return try_execute_select(self.st.db_client.connection, sql, ())


if __name__ == "__main__":
    from dispatcherWK12 import lock_ship

    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    # 3, 4,5,6,7,8,9
    # A is the surveyor
    ship_suffix = sys.argv[2] if len(sys.argv) > 2 else "2"
    ship = f"{agent}-{ship_suffix}"
    params = {"ship_type": "SHIP_PROBE"}
    bhvr = MonitorPrices(agent, f"{ship}", params)
    lock_ship(ship, "MANUAL", bhvr.connection, duration=120)
    set_logging(logging.DEBUG)
    bhvr.run()
    lock_ship(ship, "", bhvr.connection, duration=0)
