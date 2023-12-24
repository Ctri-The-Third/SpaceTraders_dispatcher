import sys
import time

sys.path.append(".")

from behaviours.generic_behaviour import Behaviour
import logging
from straders_sdk.utils import try_execute_select, set_logging, waypoint_slicer
from straders_sdk.models import Waypoint, System

BEHAVIOUR_NAME = "GO_BUY_A_SHIP"
SAFETY_PADDING = 60


class GoAndBuyShip(Behaviour):
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

    def run(self):
        super().run()
        st = self.st
        ship = self.ship
        agent = st.view_my_self()
        st.logging_client.log_beginning(
            BEHAVIOUR_NAME,
            ship.name,
            agent.credits,
            behaviour_params=self.behaviour_params,
        )

        target_ship_type = self.behaviour_params.get("ship_type", None)
        target_wp = self.find_shipyards(target_ship_type)
        if not target_wp:
            time.sleep(SAFETY_PADDING)
            self.end()
            return
        target_sys = waypoint_slicer(target_wp.symbol)
        self.ship_extrasolar_jump(waypoint_slicer)
        self.ship_intrasolar(target_wp.symbol)

        resp = st.ships_purchase(target_ship_type, target_wp.symbol)
        if not resp:
            time.sleep(SAFETY_PADDING)
            self.end()
            return
        self.end()

    def find_shipyards(self, ship_symbol):
        sql = """select shipyard_symbol, ship_type, ship_cost, (
                select round(avg(ship_cost),2)
		        from shipyard_types 
		        where ship_type = %s) 
            from shipyard_types 
            where ship_type = %s and ship_cost is not null"""
        results = try_execute_select(self.connection, sql, (ship_symbol, ship_symbol))

        current_system = self.st.systems_view_one(self.ship.nav.system_symbol)
        current_waypoint = self.st.waypoints_view_one(self.ship.nav.waypoint_symbol)
        max_cpd = float("inf")

        best_dest = None

        for result in results:
            dest_system = self.st.systems_view_one(waypoint_slicer(result[0]))
            dest_waypoint = self.st.waypoints_view_one(result[0])
            if dest_system == current_system:
                if current_waypoint == dest_waypoint:
                    cpd = (result[2] or result[3]) / 1
                else:
                    distance = self.pathfinder.calc_distance_between(
                        current_waypoint, dest_waypoint
                    )
                    cpd = (result[2] or result[3]) / ((max(distance, 15)))
            else:
                distance = self.pathfinder.calc_distance_between(
                    current_system, dest_system
                )
                cpd = (result[2] or result[3]) / (distance)
            if cpd > max_cpd or not best_dest:
                best_dest = dest_waypoint
                max_cpd = cpd
        return best_dest


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "1"
    ship = f"{agent}-{ship_number}"
    behaviour_params = {"ship_type": "SHIP_EXPLORER"}
    bhvr = GoAndBuyShip(agent, ship, behaviour_params or {})
    lock_ship(ship, "MANUAL", bhvr.st.db_client.connection, 60 * 24)
    bhvr.run()
    lock_ship(ship, "MANUAL", bhvr.st.db_client.connection, 0)
