import sys
import time


sys.path.append(".")
import random
from behaviours.generic_behaviour import Behaviour
import logging
from straders_sdk.utils import try_execute_select, set_logging, waypoint_slicer
from straders_sdk.models import Waypoint, System

BEHAVIOUR_NAME = "SingleStableTrade"
SAFETY_PADDING = 60


class SingleStableTrade(Behaviour):
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
        st = self.st
        ship = self.ship = st.ships_view_one(self.ship_name, True)

        agent = st.view_my_self()
        st.logging_client.log_beginning(BEHAVIOUR_NAME, ship.name, agent.credits)

        # to the nearest factor of 10
        target_trade_depth = get_best_tradevolume(ship.cargo_capacity)
        trade_routes = self.get_trade_routes(
            limit=5, min_market_depth=target_trade_depth
        )
        selected_random_route = random.choice(trade_routes)
        if not selected_random_route:
            # no profitable trade routes at the moment! Pause and let the conductor give us a new behaviour
            time.sleep(SAFETY_PADDING)
            st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
            self.end()
            return
        (
            trade_symbol,
            export_market_s,
            import_market_s,
            profit_per_unit,
        ) = selected_random_route
        export_market_wp = st.waypoints_view_one(
            waypoint_slicer(export_market_s), export_market_s
        )
        import_market_wp = st.waypoints_view_one(
            waypoint_slicer(import_market_s), import_market_s
        )
        export_market = st.system_market(export_market_wp)
        import_market = st.system_market(import_market_wp)
        export_market_price = export_market.get_tradegood(trade_symbol).purchase_price
        import_market_price = import_market.get_tradegood(trade_symbol).sell_price
        if (import_market_price - export_market_price) < (profit_per_unit / 2):
            time.sleep(SAFETY_PADDING)
            st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
            self.end()
            return

        self.ship_extrasolar(st.systems_view_one(waypoint_slicer(export_market_s)))
        self.ship_intrasolar(export_market_s)
        self.st.ship_dock(ship)
        self.purchase_what_you_can(trade_symbol, ship.cargo_space_remaining)
        self.ship_extrasolar(st.systems_view_one(waypoint_slicer(import_market_s)))
        self.ship_intrasolar(import_market_s)
        self.sell_all_cargo([], import_market)
        st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
        self.end()

    def get_trade_routes(
        self, limit=10, min_market_depth=100, max_market_depth=1000000
    ) -> list[tuple]:
        sql = """select route_value, system_symbol, trade_symbol, profit_per_unit, export_market, import_market, market_depth
        from trade_routes_intrasystem tris
        where market_depth >= %s
        and market_depth <= %s
        limit %s"""
        routes = try_execute_select(
            self.connection, sql, (min_market_depth, max_market_depth, limit)
        )
        if not routes:
            return []

        return [(r[2], r[4], r[5], r[3]) for r in routes]


def get_best_tradevolume(number) -> int:
    depth = 10
    while number / 10 > 1:
        depth *= 10
        number /= 10
    return depth


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "7"
    ship = f"{agent}-{ship_number}"
    behaviour_params = {}
    bhvr = SingleStableTrade(agent, ship, behaviour_params or {})
    lock_ship(ship, "MANUAL", bhvr.st.db_client.connection, 60 * 24)
    bhvr.run()
    lock_ship(ship, "MANUAL", bhvr.st.db_client.connection, 0)
