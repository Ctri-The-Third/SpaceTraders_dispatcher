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
from straders_sdk.contracts import Contract
from straders_sdk.models import Market, Waypoint
from straders_sdk.utils import waypoint_slicer, set_logging, try_execute_select
from straders_sdk.constants import SUPPLY_LEVELS
import math
from behaviours.generic_behaviour import Behaviour
from conductor_functions import process_contracts

BEHAVIOUR_NAME = "EXECUTE_CONTRACTS"
SAFETY_PADDING = 180


class ExecuteContracts(Behaviour):
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

    def default_params_obj(self):
        return_obj = super().default_params_obj()
        return return_obj

    def run(self):
        super().run()
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

        process_contracts(st, False)

        self.behaviour_params = self.behaviour_params | self.select_active_contract()
        params = self.behaviour_params
        if "quantity" not in params:
            self.logger.warning("No active contract found, sleeping")
            self.st.sleep(SAFETY_PADDING)
            return
        quantity = params["quantity"]
        buy_system = st.systems_view_one(waypoint_slicer(params["buy_wp"]))
        buy_wp = st.waypoints_view_one(params["buy_wp"])
        fulfil_sys = st.systems_view_one(waypoint_slicer(params["fulfil_wp"]))
        fulfil_wp = st.waypoints_view_one(params["fulfil_wp"])
        tradegood = params["tradegood"]

        if tradegood not in [s.symbol for s in ship.cargo_inventory]:
            self.go_and_buy(params["tradegood"], buy_wp, max_to_buy=quantity)

        self.go_and_sell_or_fulfill(params["tradegood"], fulfil_wp)

    def select_active_contract(self):
        contracts = self.st.view_my_contracts()
        open_contracts = [
            c for c in contracts if c.accepted and not c.fulfilled and not c.is_expired
        ]
        for contract in open_contracts:
            for deliverable in contract.deliverables:
                if deliverable.units_fulfilled == deliverable.units_required:
                    continue
                sql = """SELECT route_value, system_symbol, trade_symbol, profit_per_unit, export_market, export_x, export_y, purchase_price, fulfill_value_per_unit, fulfill_market, supply_text, supply_value, market_depth, waypoint_symbol, fulfil_x, fulfil_y, distance, agent_symbol
	FROM public.trade_routes_contracts
    where system_symbol = %s and trade_symbol = %s
    and agent_symbol = %s"""
                results = try_execute_select(
                    sql,
                    (
                        self.ship.nav.system_symbol,
                        deliverable.symbol,
                        self.agent.symbol,
                    ),
                )
                if not results:
                    continue
                params = {
                    "tradegood": results[0][2],
                    "buy_wp": results[0][4],
                    "fulfil_wp": results[0][9],
                    "quantity": deliverable.units_required
                    - deliverable.units_fulfilled,
                }
                return params
        return {}

    def select_positive_trade(self):
        # this gets all viable trades for a given system
        # it lists all the trades from the current market first, then all others afterwards#
        # it will then go by the most profitable (profit per distance).
        contracts = self.st.view_my_contracts()
        open_contracts = [
            c for c in contracts if c.accepted and not c.fulfilled and not c.is_expired
        ]

        sql = """
    SELECT route_value, system_symbol, trade_symbol, profit_per_unit, export_market, export_x, export_y, purchase_price, sell_price, supply_value, supply_text, import_supply, market_depth, import_market, import_x, import_y, distance
	FROM public.trade_routes_intrasystem
    where system_symbol = %s
    order by export_market = %s desc, route_value desc
    """
        results = try_execute_select(
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
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "D"
    ship = f"{agent}-{ship_number}"
    behaviour_params = {
        "priority": 3,
    }

    bhvr = ExecuteContracts(agent, ship, behaviour_params or {})

    while True:
        lock_ship(ship, "MANUAL", 60 * 24)
        bhvr.run()
    lock_ship(ship_number, "MANUAL", 0)
