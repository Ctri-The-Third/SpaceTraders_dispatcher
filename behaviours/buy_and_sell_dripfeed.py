# This behaviour will go extrasoloar to the best place for a given item
#  then take it to the assigned location/ship and then transfer/sell the cargo


import sys

sys.path.append(".")
from straders_sdk.utils import waypoint_slicer, try_execute_select, set_logging
from behaviours.generic_behaviour import Behaviour
import logging
import time
import math
from straders_sdk.responses import SpaceTradersResponse
from straders_sdk.local_response import LocalSpaceTradersRespose
from straders_sdk.client_api import SpaceTradersApiClient as SpaceTraders
from datetime import datetime, timedelta

BEHAVIOUR_NAME = "BUY_AND_SELL_DRIPFEED"
SAFETY_PADDING = 300


class BuyAndSellDripfeed(Behaviour):
    """Requires a parameter blob containing

    `tradegood`: the symbol of the tradegood to buy\n
    optional:\n
    `buy_wp`: if you want to specify a source market, provide the symbol.\n
    `sell_wp`: if you want the ship to sell the cargo, set which waypoint\n
    `max_buy_price`: if you want to limit the purchase price, set it here\n
    `min_sell_price`: if you want to limit the sell price, set it here\n
    """

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
        self.logger = logging.getLogger("bhvr_receive_and_fulfill")

        self.max_purchase_price = 0
        self.min_sell_price = 0
        self.purchase_market = ""
        self.sell_market = ""
        self.target_tradegood = ""

    def run(self):
        super().run()
        st = self.st
        ship = self.ship = self.st.ships_view_one(self.ship.name, True)
        agent = self.agent
        st.logging_client.log_beginning(BEHAVIOUR_NAME, ship.name, agent.credits)

        #
        # setup initial parameters and preflight checks
        #

        if "tradegood" not in self.behaviour_params:
            time.sleep(SAFETY_PADDING)
            self.logger.error("No tradegood specified for ship %s", ship.name)
            raise ValueError("No tradegood specified for ship %s" % ship.name)
        self.target_tradegood = self.behaviour_params["tradegood"]
        if "buy_wp" in self.behaviour_params:
            self.purchase_market = self.behaviour_params["buy_wp"]
        if "max_buy_price" in self.behaviour_params:
            self.max_purchase_price = self.behaviour_params["max_buy_price"]

        if "sell_wp" in self.behaviour_params:
            self.sell_market = self.behaviour_params["sell_wp"]
        if "min_sell_price" in self.behaviour_params:
            self.min_sell_price = self.behaviour_params["min_sell_price"]

        if not self.purchase_market:
            markets = self.find_cheapest_markets_for_good(self.target_tradegood)
            if not markets:
                self.end(f"no markets found for {self.target_tradegood}")
                return
            self.purchase_market = markets[0]
        if not self.sell_market:
            markets = self.find_best_market_systems_to_sell(self.target_tradegood)
            if not markets:
                self.end(f"no markets found for {self.target_tradegood}")
                return
            self.sell_market = markets[0][0]
        ready = False
        if ship.nav.waypoint_symbol == self.sell_market and ship.cargo_units_used > 0:
            self.sell_half()
        else:
            ready = self.buy_half()

        if ready:
            self.sell_half()
        # check if we are at the sell market and have some cargo in our inventory - if so, sell half.
        # if not, buy half

    def buy_half(self):
        ship = self.ship
        st = self.st
        self.ship_extrasolar(st.systems_view_one(waypoint_slicer(self.purchase_market)))
        self.ship_intrasolar(self.purchase_market)
        # check if the export price is below the max purchase price
        # if it is, buy 1 tradevolume, and check the price and repeat.
        # if not, sleep for 5 minutes then try again
        # if full, head to the sell market
        # once at sell market, check if import price is above the min sell price
        # if it is, sell 1 tradevolume, and check the price and repeat.
        # if not, sleep for 5 minutes then try again
        purchase_market_wp = self.st.waypoints_view_one(
            waypoint_slicer(self.purchase_market), self.purchase_market
        )
        tradegood = self.st.system_market(purchase_market_wp).get_tradegood(
            self.target_tradegood
        )
        if tradegood.recorded_ts < datetime.now() - timedelta(minutes=15):
            self.log_market_changes(self.purchase_market)

        while ship.cargo_space_remaining > 0:
            purchase_market_mkt = self.st.system_market(purchase_market_wp)
            tradegood = purchase_market_mkt.get_tradegood(self.target_tradegood)
            if (
                self.max_purchase_price > 0
                and tradegood.purchase_price > self.max_purchase_price
            ):
                time.sleep(300)
                return False
            amount_to_buy = min(ship.cargo_space_remaining, tradegood.trade_volume)
            resp = self.buy_cargo(self.target_tradegood, amount_to_buy)
            if not resp:
                self.logger.error(
                    "Couldn't buy %d units of %s at %s",
                    amount_to_buy,
                    self.target_tradegood,
                    self.purchase_market,
                )
                return ship.cargo_units_used > 0
        return True

    def sell_half(self):
        ship = self.ship
        sell_system = self.st.systems_view_one(waypoint_slicer(self.sell_market))
        self.ship_extrasolar(sell_system)
        self.ship_intrasolar(self.sell_market)
        sell_market_wp = self.st.waypoints_view_one(
            waypoint_slicer(self.sell_market), self.sell_market
        )
        tradegood = self.st.system_market(sell_market_wp).get_tradegood(
            self.target_tradegood
        )
        if tradegood.recorded_ts < datetime.now() - timedelta(minutes=15):
            self.log_market_changes(self.sell_market)
        while ship.cargo_units_used > 0:
            sell_market_mkt = self.st.system_market(sell_market_wp)
            tradegood = sell_market_mkt.get_tradegood(self.target_tradegood)
            if self.min_sell_price > 0 and tradegood.sell_price > self.min_sell_price:
                time.sleep(300)
                return
            amount_to_sell = min(ship.cargo_units_used, tradegood.trade_volume)
            self.sell_cargo(self.target_tradegood, amount_to_sell, sell_market_mkt)

    def end(self, error):
        super().end()
        self.st.logging_client.log_ending(
            BEHAVIOUR_NAME, self.ship.name, self.agent.credits
        )
        if error:
            self.logger.error(error)
            time.sleep(SAFETY_PADDING)

    def find_cheapest_markets_for_good(self, tradegood_sym: str) -> list[str]:
        sql = """select market_symbol from market_tradegood_listings
where trade_symbol = %s
order by purchase_price asc """
        wayps = try_execute_select(self.connection, sql, (tradegood_sym,))

        if not wayps:
            self.logger.error(
                "Couldn't find cheapest market for good %s", tradegood_sym
            )
            return wayps
        return [wayp[0] for wayp in wayps]


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    suffix = sys.argv[2] if len(sys.argv) > 2 else "7"
    ship = f"{agent}-{suffix}"
    bhvr = BuyAndSellDripfeed(
        agent,
        ship,
        behaviour_params={
            "buy_wp": "X1-U49-F51",
            "sell_wp": "X1-U49-D45",
            "tradegood": "ELECTRONICS",
            "max_buy_price": 1617.00,
            "min_sell_price": 5010.00,
        },
    )
    lock_ship(ship, "MANUAL", bhvr.st.db_client.connection, duration=120)
    set_logging(logging.DEBUG)

    bhvr.run()
    lock_ship(ship, "MANUAL", bhvr.st.db_client.connection, duration=0)
