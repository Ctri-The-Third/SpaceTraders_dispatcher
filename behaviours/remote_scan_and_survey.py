import sys

sys.path.append(".")
from behaviours.generic_behaviour import Behaviour
from straders_sdk import SpaceTraders
from straders_sdk.models import Waypoint, System
from straders_sdk.utils import waypoint_slicer, try_execute_select, set_logging
import time
import math
import logging

BEHAVIOUR_NAME = "SCAN_WAYPOINTS_AND_SURVEY"


class RemoteScanWaypoints(Behaviour):
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

    def run(self):
        super().run()
        ship = self.ship
        agent = self.agent
        hq_system = waypoint_slicer(agent.headquarters)
        st = self.st
        # check all markets in the system
        st.logging_client.log_beginning(
            BEHAVIOUR_NAME, ship.name, agent.credits, self.behaviour_params
        )

        agent = self.agent
        if ship.can_survey:
            asteroid_field = self.behaviour_params.get("asteroid_wp", None)
            if not asteroid_field:
                asteroid_field = st.find_waypoints_by_type_one(
                    hq_system, "ASTEROID_FIELD"
                )
                if asteroid_field:
                    asteroid_field = asteroid_field.symbol
                else:
                    asteroid_field = ship.nav.waypoint_symbol
            # move the ship to the asteroid field.
            self.ship_intrasolar(asteroid_field, False)

        # check the total number of systems by pinging the status.
        # get all systems a page at a time (new function? expand function?)
        # whilst getting systems, survey continually.

        #
        # get all unscanned systems
        #
        systems_sweep = self.have_we_all_the_systems()
        if not systems_sweep[0]:
            for i in range(1, math.ceil(systems_sweep[1] / 20) + 1):
                print(i)
                resp = st.systems_view_twenty(i, True)
                while not resp:
                    time.sleep(20)
                    resp = st.systems_view_twenty(i, True)
                    self.logger.warn("Failed to get system - page %s - retrying", i)
                if not resp:
                    self.logger.error(
                        "Failed to get system - page %s - redo this later!", i
                    )
                if ship.seconds_until_cooldown > 0:
                    continue
                if ship.nav.travel_time_remaining > 0:
                    continue
                if ship.can_survey:
                    st.ship_survey(ship)
                time.sleep(1.2)
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
            resp = st.waypoints_view_one(wayp[0], True)
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

            wp = st.waypoints_view_one(jump_gate_sym)
            if not wp.is_charted:
                wp = st.waypoints_view_one(jump_gate_sym, True)
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
            wp = st.waypoints_view_one(wp_sym)
            if wp.has_market:
                resp = st.system_market(wp, True)
                time.sleep(1.2)
            if wp.has_shipyard:
                resp = st.system_shipyard(wp, True)
                time.sleep(1.2)
            if ship.can_survey:
                st.ship_survey(ship)
                time.sleep(0.5)

        if len(wayps) + len(rows) == 0:
            self.logger.warning(
                "No unscanned waypoints found. stalling for 10 minutes and exiting."
            )
            time.sleep(600)

        # orbital stations
        # asteroid fields

        # refresh shipyards and markets (note, will get basic data for most)
        # tag uncharted, marketplace, and shipyard systems for visit
        # stop surveying and depart.

        # jump to system
        # explore system
        # return to gate
        self.end()

        st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)

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

    def have_we_all_the_systems(self):
        sql = """select count(distinct system_symbol) from systems"""
        cursor = self.st.db_client.connection.cursor()
        cursor.execute(sql, ())
        row = cursor.fetchone()
        db_systems = row[0]

        status = self.st.game_status()
        api_systems = status.total_systems
        return (db_systems >= api_systems, status.total_systems)

    def recursive_fetch_navgate_systems(
        self, system_symbol: str, collected_system_symbols: list[str] = list()
    ) -> list[str]:
        # does the system have a warp gate? should be yes.
        # takes a good half hour. Might have limitations based on charting and not work straight away?
        resp = gate_wp = self.st.find_waypoints_by_type_one(system_symbol, "JUMP_GATE")
        if not resp:
            return collected_system_symbols

        gate = self.st.system_jumpgate(gate_wp)
        if not resp:
            return collected_system_symbols

        if system_symbol in collected_system_symbols:
            print(
                f"({len(collected_system_symbols)}){system_symbol} - Whoops, already got this system! "
            )
            return collected_system_symbols
        else:
            print(
                f"({len(collected_system_symbols)}){system_symbol} - adding and checking direct connects"
            )
            collected_system_symbols.append(system_symbol)
            for system in gate.connected_waypoints:
                self.recursive_fetch_navgate_systems(
                    system.symbol, collected_system_symbols
                )

    def scan_local_system(self):
        st = self.st
        ship = self.ship
        current_system_sym = self.ship.nav.system_symbol
        # situation - when loading the waypoints, we get the systemWaypoint aggregate that doesn't have traits or other info.
        # QUESTION
        st.waypoints_view(current_system_sym, True)
        target_wayps = []
        marketplaces = (
            st.find_waypoints_by_trait(current_system_sym, "MARKETPLACE") or []
        )
        shipyards = st.find_waypoints_by_trait(current_system_sym, "SHIPYARD") or []
        gate = st.find_waypoints_by_type_one(current_system_sym, "JUMP_GATE")
        target_wayps.extend(marketplaces)
        target_wayps.extend(shipyards)
        target_wayps.append(gate)

        start = st.waypoints_view_one(ship.nav.waypoint_symbol)
        path = nearest_neighbour(target_wayps, start)

        for wayp_sym in path:
            waypoint = st.waypoints_view_one(wayp_sym)

            self.ship_intrasolar(wayp_sym)

            trait_symbols = [trait.symbol for trait in waypoint.traits]
            if "MARKETPLACE" in trait_symbols:
                market = st.system_market(waypoint, True)
                if market:
                    for listing in market.listings:
                        print(
                            f"item: {listing.symbol}, buy: {listing.purchase} sell: {listing.sell_price} - supply available {listing.supply}"
                        )
            if "SHIPYARD" in trait_symbols:
                shipyard = st.system_shipyard(waypoint, True)
                if shipyard:
                    for ship_type in shipyard.ship_types:
                        print(ship_type)
            if waypoint.type == "JUMP_GATE":
                jump_gate = st.system_jumpgate(waypoint, True)


def nearest_neighbour(waypoints: list[Waypoint], start: Waypoint):
    path = []
    unplotted = waypoints
    current = start
    while unplotted:  # whlist there are unplotted waypoints needing visited
        # note that we are not iterating over the contents, so it's safe to delete from the inside.

        # find the closest waypoint.
        # for each entry in unplotted,
        #   pass it as "wp" to the calculate_distance function
        #   return the minimum value of those returned by the function.
        next_waypoint = min(unplotted, key=lambda wp: calculate_distance(current, wp))
        path.append(next_waypoint.symbol)
        unplotted.remove(next_waypoint)
        current = next_waypoint
    return path


def nearest_neighbour_systems(systems: list[System], start: System):
    path = []
    unplotted = systems
    current = start
    while unplotted:
        next_system = min(unplotted, key=lambda sys: calculate_distance(current, sys))
        path.append(next_system.symbol)
        unplotted.remove(next_system)
        current = next_system
    return path


def calculate_distance(src: Waypoint, dest: Waypoint):
    return math.sqrt((src.x - dest.x) ** 2 + (src.y - dest.y) ** 2)


if __name__ == "__main__":
    from dispatcherWK12 import lock_ship

    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    # 3, 4,5,6,7,8,9
    # A is the surveyor
    ship_suffix = sys.argv[2] if len(sys.argv) > 2 else "4"
    ship = f"{agent}-{ship_suffix}"

    bhvr = RemoteScanWaypoints(
        agent, ship, behaviour_params={"asteroid_wp": "X1-CN90-02905X"}
    )
    lock_ship(ship, "MANUAL", bhvr.connection, duration=120)
    set_logging(logging.DEBUG)
    bhvr.run()
    lock_ship(ship, "", bhvr.connection, duration=0)

    set_logging(level=logging.DEBUG)
