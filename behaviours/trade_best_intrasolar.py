# takes a tradegood. Then trades that to ensure that the market is LIMITED
# if the export activity hits RESTRICTED, it switches to finding profitable import goods until that clears.

# script is happy to work to 0 profit, but will not work at a loss.


import time
import sys


sys.path.append(".")
from behaviours.generic_behaviour import Behaviour
import logging
from straders_sdk.ship import Ship
from straders_sdk.models import Market, Waypoint
from straders_sdk.utils import waypoint_slicer, set_logging, try_execute_select
from straders_sdk.constants import SUPPLY_LEVELS
from behaviours.generic_behaviour import Behaviour
import random

BEHAVIOUR_NAME = "TRADE_BEST_INTRASOLAR"
SAFETY_PADDING = 180


class TradeBestInSystem(Behaviour):
    def __init__(
        self,
        agent_name,
        ship_name,
        behaviour_params: dict = ...,
        config_file_name="user.json",
        session=None,
    ) -> None:
        super().__init__(
            agent_name,
            ship_name,
            behaviour_params,
            config_file_name,
            session,
        )
        self.agent = self.st.view_my_self()
        self.logger = logging.getLogger(BEHAVIOUR_NAME)

    def default_params_obj(self):
        return_obj = super().default_params_obj()
        return return_obj

    def run(self):
        super().run()
        self.st.logging_client.log_beginning(
            BEHAVIOUR_NAME,
            self.ship.name,
            self.agent.credits,
            behaviour_params=self.behaviour_params,
        )
        self.sleep_until_ready()

        self._run()
        self.end()

    def _run(self):
        st = self.st
        ship = self.ship  # = st.ships_view_one(self.ship_name, True)
        ship: Ship
        agent = self.agent
        self.sleep_until_arrived()
        best_trade = self.get_best_trade()
        if not best_trade:
            self.logger.info("No trade found")
            self.st.sleep(SAFETY_PADDING)
            return

        (
            trade_symbol,
            system_symbol,
            export_market,
            market_depth,
            sell_price,
            import_market,
        ) = best_trade

        export_market = st.waypoints_view_one(export_market)
        import_market = st.waypoints_view_one(import_market)
        if trade_symbol not in [c.symbol for c in ship.cargo_inventory]:
            have_cargo = self.go_and_buy(
                trade_symbol, export_market, burn_allowed=True, max_to_buy=market_depth
            )
        else:
            have_cargo = True

        if have_cargo:
            self.go_and_sell_or_fulfill(trade_symbol, import_market, burn_allowed=True)
        else:
            self.logger.info("No cargo to sell")
            self.st.sleep(SAFETY_PADDING)
        # your code goes here

    def get_best_trade(self):
        sql = """SELECT trade_symbol,  system_symbol,  export_market, market_depth, sell_price, import_market
	FROM public.trade_routes_intrasystem
    where system_symbol = %s;"""
        results = try_execute_select(
            sql, (self.ship.nav.system_symbol,), self.st.connection
        )
        if not results:
            return None
        best_trade = results[0]
        return (
            best_trade[0],
            best_trade[1],
            best_trade[2],
            best_trade[3],
            best_trade[4],
            best_trade[5],
        )


#
# to execute from commandline, run the script with the agent and ship_symbol as arguments, or edit the values below
#
if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "11"
    ship = f"{agent}-{ship_number}"
    behaviour_params = {
        "priority": 3,
    }

    bhvr = TradeBestInSystem(agent, ship, behaviour_params or {})

    lock_ship(ship, "MANUAL", 60 * 24)

    bhvr.run()
    lock_ship(ship, "MANUAL", 0)
