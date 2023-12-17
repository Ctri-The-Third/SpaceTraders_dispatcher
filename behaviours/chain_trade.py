# takes a tradegood. Then trades that to ensure that the market is LIMITED
# if the export activity hits RESTRICTED, it switches to finding profitable import goods until that clears.

# script is happy to work to 0 profit, but will not work at a loss.


import time
import sys


sys.path.append(".")
from behaviours.generic_behaviour import Behaviour
from behaviours.buy_and_deliver_or_sell import BuyAndDeliverOrSell_6
import logging

from datetime import datetime, timedelta
from straders_sdk.client_api import SpaceTradersApiClient as SpaceTraders
from straders_sdk.ship import Ship
from straders_sdk.models import Market, Waypoint
from straders_sdk.utils import waypoint_slicer, set_logging, try_execute_select
from straders_sdk.constants import SUPPLY_LEVELS
import math
from behaviours.generic_behaviour import Behaviour

BEHAVIOUR_NAME = "CHAIN_TRADES"
SAFETY_PADDING = 60


class ChainTrade(BuyAndDeliverOrSell_6):
    def __init__(
        self,
        agent_name,
        ship_name,
        behaviour_params: dict = ...,
        config_file_name="user.json",
        session=None,
        connection=None,
    ) -> None:
        Behaviour.__init__(
            self,
            agent_name,
            ship_name,
            behaviour_params,
            config_file_name,
            session,
            connection,
        )
        self.agent = self.st.view_my_self()
        self.logger = logging.getLogger(BEHAVIOUR_NAME)

    def run(self):
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

        params = self.select_positive_trade()

        buy_system = st.systems_view_one(waypoint_slicer(params["buy_wp"]))
        buy_wp = st.waypoints_view_one(buy_system.symbol, params["buy_wp"])
        sell_sys = st.systems_view_one(waypoint_slicer(params["sell_wp"]))
        sell_wp = st.waypoints_view_one(sell_sys.symbol, params["sell_wp"])
        self.fetch_half(
            "",
            buy_system,
            buy_wp,
            [],
            self.ship.cargo_capacity,
            params["tradegood"],
        )

        self.deliver_half(self.ship.nav.system_symbol, sell_wp, params["tradegood"])

    def select_positive_trade(self):
        # this gets all viable trades for a given system
        # it lists all the trades from the current market first, then all others afterwards#
        # it will then go by the most profitable (profit per distance).

        sql = """
    SELECT route_value, system_symbol, trade_symbol, profit_per_unit, export_market, export_x, export_y, purchase_price, sell_price, supply_value, supply_text, import_supply, market_depth, import_market, import_x, import_y, distance
	FROM public.trade_routes_intrasystem
    where system_symbol = %s
    order by export_market = %s desc, route_value desc
    """
        results = try_execute_select(
            self.st.db_client.connection,
            sql,
            (self.ship.nav.system_symbol, self.ship.nav.waypoint_symbol),
        )
        if not results:
            return []
        params = {
            "tradegood": results[0][2],
            "buy_wp": results[0][4],
            "sell_wp": results[0][13],
            "quantity": self.ship.cargo_capacity,
            # half of sellprice - buyprice
            "safety_profit_threshold": (results[0][8] - results[0][7]) / 2,
        }
        return params


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "1"
    ship = f"{agent}-{ship_number}"
    behaviour_params = {
        "priority": 3,
    }

    bhvr = ChainTrade(agent, ship, behaviour_params or {})

    lock_ship(ship_number, "MANUAL", bhvr.st.db_client.connection, 60 * 24)
    bhvr.run()
    lock_ship(ship_number, "MANUAL", bhvr.st.db_client.connection, 0)
