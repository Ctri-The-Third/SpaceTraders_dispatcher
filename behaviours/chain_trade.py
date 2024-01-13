# takes a tradegood. Then trades that to ensure that the market is LIMITED
# if the export activity hits RESTRICTED, it switches to finding profitable import goods until that clears.

# script is happy to work to 0 profit, but will not work at a loss.


import time
import sys


sys.path.append(".")
from behaviours.generic_behaviour import Behaviour
import logging

from datetime import datetime, timedelta
from straders_sdk.client_api import SpaceTradersApiClient as SpaceTraders
from straders_sdk.ship import Ship
from straders_sdk.models import Market, Waypoint
from straders_sdk.utils import waypoint_slicer, set_logging, try_execute_select
from straders_sdk.constants import SUPPLY_LEVELS
import math
from behaviours.generic_behaviour import Behaviour
import random

BEHAVIOUR_NAME = "CHAIN_TRADES"
SAFETY_PADDING = 180


class ChainTrade(Behaviour):
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
        self.agent = self.st.view_my_self()
        self.logger = logging.getLogger(BEHAVIOUR_NAME)

        self.target_sys_symbol = behaviour_params.get("target_sys", None)

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
        ship = self.ship  # = st.ships_view_one(self.ship_name, True)
        ship: Ship
        agent = self.agent

        if self.target_sys_symbol:
            self.ship_extrasolar_jump(self.target_sys_symbol)

        start_sys = st.systems_view_one(ship.nav.system_symbol)
        self.start_wp = st.waypoints_view_one(ship.nav.waypoint_symbol)
        params = self.select_positive_trade()
        if not params:
            self.logger.info("No trades found")

            # go and tour possible markets
            self.scan_local_system()
            self.st.release_connection()
            self.st.sleep(SAFETY_PADDING)
            return

        buy_wp = st.waypoints_view_one(params["buy_wp"])
        sell_wp = st.waypoints_view_one(params["sell_wp"])
        tradegood = params["tradegood"]
        pass
        if not tradegood in [x.symbol for x in ship.cargo_inventory]:
            self.go_and_buy(
                tradegood,
                buy_wp,
                max_to_buy=self.ship.cargo_capacity,
                burn_allowed=True,
            )

        self.go_and_sell_or_fulfill(tradegood, sell_wp, burn_allowed=True)

    def select_positive_trade(self):
        # this gets all viable trades for a given system
        # it lists all the trades from the current market first, then all others afterwards#
        # it will then go by the most profitable (profit per distance).
        results = None
        if len(self.ship.cargo_inventory) > 0:
            cargo_symbols = tuple([c.symbol for c in self.ship.cargo_inventory])
            sql = """
    SELECT route_value, system_symbol, trade_symbol, profit_per_unit, export_market, export_x, export_y, purchase_price, sell_price, supply_value,  supply_text, import_supply, market_depth, import_market, import_x, import_y, distance, export_activity
	FROM public.trade_routes_intrasystem
    where system_symbol = %s
    and trade_Symbol in %s
    and purchase_price < %s
    and ((supply_value >= 4 and export_activity = 'STRONG') or supply_value >= 3)
    order by export_market = %s desc, route_value desc
    """
            results = try_execute_select(
                sql,
                (
                    self.ship.nav.system_symbol,
                    cargo_symbols,
                    self.agent.credits,
                    self.ship.nav.waypoint_symbol,
                ),
                self.connection,
            )
        if not results:
            sql = """   SELECT route_value, system_symbol, trade_symbol, profit_per_unit, export_market, export_x, export_y, purchase_price, sell_price, supply_value,  supply_text, import_supply, market_depth, import_market, import_x, import_y, distance, export_activity
	FROM public.trade_routes_intrasystem
    where system_symbol = %s
    
    and purchase_price < %s
    and ((supply_value >= 4 and export_activity = 'STRONG') or supply_value >= 3)
    order by export_market = %s desc, route_value desc"""
            results = try_execute_select(
                sql,
                (
                    self.ship.nav.system_symbol,
                    self.agent.credits,
                    self.ship.nav.waypoint_symbol,
                ),
                self.connection,
            )
        if not results:
            return {}
        best_distance = float("inf")
        best_result = None
        for result in results:
            dest = Waypoint(
                result[1],
                result[4],
                "",
                result[5],
                result[6],
                [],
                [],
                {},
                {},
                [],
                False,
            )
            if result[4] == self.ship.nav.waypoint_symbol:
                best_result = result
                break
            if (
                self.pathfinder.calc_distance_between(self.start_wp, dest)
                < best_distance
            ):
                best_distance = self.pathfinder.calc_distance_between(
                    self.start_wp, dest
                )
                best_result = result
            if best_distance == 0:
                break
        if not best_result:
            return []
        best_result = random.choice(results)
        params = {
            "tradegood": best_result[2],
            "buy_wp": best_result[4],
            "sell_wp": best_result[13],
            "quantity": self.ship.cargo_capacity,
            # half of sellprice - buyprice
            "safety_profit_threshold": (best_result[8] - best_result[7]) / 2,
        }
        return params


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "5A"
    ship = f"{agent}-{ship_number}"
    behaviour_params = {
        "priority": 3,
        "target_sys": "X1-BM12",
        "script_name": "CHAIN_TRADES",
    }

    bhvr = ChainTrade(agent, ship, behaviour_params or {})

    lock_ship(ship, "MANUAL", 60 * 24)

    bhvr.run()
    lock_ship(ship, "MANUAL", 0)
