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

BEHAVIOUR_NAME = "EMERGENCY_REBOOT"
SAFETY_PADDING = 60


class EmergencyReboot(Behaviour):
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

        self.asteroid_wp = self.behaviour_params.get("asteroid_wp", None)
        self.sell_wp = self.behaviour_params.get("sell_wp", None)

    def run(self):
        super().run()
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

        # find the gas giant if not set as asteroid_wp
        # travel there and siphon hydrocarbon until full
        # find the market that imports h
        # ydrocarbon and exports fuel
        # travel there, sell, refuel.
        if not ship.can_siphon:
            self.logger.error(
                "Ship cannot siphon - this behaviour should only be used by the COMMANDER or an EXPLORER"
            )
            return

        if not self.asteroid_wp:
            try:
                self.asteroid_wp = self.st.find_waypoints_by_type(
                    ship.nav.system_symbol, "GAS_GIANT"
                )[0].symbol
            except:
                self.logger.error("No gas giants found")
                return
        if not self.sell_wp:
            all_possibilties = self.find_best_market_systems_to_sell("HYDROCARBON")
            # in an emergency, we're only looking for intrasystem options.
            possibilities = [
                (sym, sys, price)
                for sym, sys, price in all_possibilties
                if sys.symbol == ship.nav.system_symbol
            ]
            # already sorted by best price
            self.sell_wp = possibilities[0][0]
        tradegood = "HYDROCARBON"

        # if we start the emergency behaviour from somewhere not in the trade route, we need to get there conserving as much fuel as possible
        if ship.nav.waypoint_symbol not in (self.asteroid_wp, self.sell_wp):
            self.ship_intrasolar(self.asteroid_wp, flight_mode="DRIFT")

        self.ship_intrasolar(self.asteroid_wp, flight_mode="CRUISE")
        self.siphon_till_full(ship.cargo_capacity)

        self.go_and_sell_or_fulfill(tradegood, self.sell_wp)
        self.jettison_all_cargo(["HYDROCARBON"])

    def select_positive_trade(self):
        # this gets all viable trades for a given system
        # it lists all the trades from the current market first, then all others afterwards#
        # it will then go by the most profitable (profit per distance).

        sql = """
    SELECT route_value, system_symbol, trade_symbol, profit_per_unit, export_market, export_x, export_y, purchase_price, sell_price, supply_value, supply_text, import_supply, market_depth, import_market, import_x, import_y, distance
	FROM public.trade_routes_intrasystem
    where system_symbol = %s
    and purchase_price < %s
    order by export_market = %s desc, route_value desc
    """
        results = try_execute_select(
            self.st.db_client.connection,
            sql,
            (
                self.ship.nav.system_symbol,
                self.agent.credits,
                self.ship.nav.waypoint_symbol,
            ),
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
    bhvr = EmergencyReboot(agent, ship, behaviour_params or {})

    lock_ship(ship_number, "MANUAL", 60 * 24)
    while True:
        bhvr.st.ships_view_one(ship, True)

        bhvr.run()
    lock_ship(ship_number, "MANUAL", 0)
