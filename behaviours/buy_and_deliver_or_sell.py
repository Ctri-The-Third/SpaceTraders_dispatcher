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

BEHAVIOUR_NAME = "BUY_AND_DELIVER_OR_SELL"
SAFETY_PADDING = 300


class BuyAndDeliverOrSell_6(Behaviour):
    """Requires a parameter blob containing

    `tradegood`: the symbol of the tradegood to buy\n
    optional:\n
    `buy_wp`: if you want to specify a source market, provide the symbol.\n
    `quantity`: the quantity to buy (defaults to max)\n
    `sell_wp`: if you want the ship to sell the cargo, set which waypoint\n
    `transfer_ship`: if you want the ship to transfer the cargo, set which ship\n
    `fulfil_wp`: if you want the ship to deliver the cargo, set which waypoint
    `return_tradegood`: if you want the ship to return to the beginning with cargo, set which cargo
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
        target_tradegood = self.behaviour_params["tradegood"]
        return_tradegood = self.behaviour_params.get("return_tradegood", None)
        start_system = st.systems_view_one(ship.nav.system_symbol)

        self.jettison_all_cargo([target_tradegood, return_tradegood])

        max_to_buy = self.behaviour_params.get("quantity", ship.cargo_space_remaining)

        end_system = None
        end_waypoint = None
        receive_ship = None
        if "buy_wp" in self.behaviour_params:
            target_waypoints = [
                self.behaviour_params["buy_wp"],
            ]
            source_wp = st.waypoints_view_one(
                waypoint_slicer(self.behaviour_params["buy_wp"]),
                self.behaviour_params["buy_wp"],
            )
        if "sell_wp" in self.behaviour_params:
            end_system = st.systems_view_one(
                waypoint_slicer(self.behaviour_params["sell_wp"])
            )
            end_waypoint = st.waypoints_view_one(
                end_system.symbol, self.behaviour_params["sell_wp"]
            )
        if "fulfil_wp" in self.behaviour_params:
            end_system = st.systems_view_one(
                waypoint_slicer(self.behaviour_params["fulfil_wp"])
            )
            end_waypoint = st.waypoints_view_one(
                end_system.symbol, self.behaviour_params["fulfil_wp"]
            )
        if "transfer_ship" in self.behaviour_params:
            receive_ship = st.ships_view_one(self.behaviour_params["transfer_ship"])
            end_system = st.systems_view_one(receive_ship.nav.system_symbol)
            end_waypoint = st.waypoints_view_one(
                end_system.symbol, receive_ship.nav.waypoint_symbol
            )

        if not target_waypoints:
            time.sleep(SAFETY_PADDING)
            self.logger.error("No waypoint found for tradegood %s", target_tradegood)
            raise ValueError("No waypoint found for tradegood %s" % target_tradegood)

        # vent any spare stuff before deploying.

        #
        # we know where we're going, we know what we're getting. Deployment.
        #

        quantity = 0
        for ship_inventory_item in ship.cargo_inventory:
            if ship_inventory_item.symbol == target_tradegood:
                quantity = ship_inventory_item.units

        if quantity > 0 and end_waypoint is not None:
            resp = self.deliver_half(end_system, end_waypoint, target_tradegood)
        else:
            resp = self.fetch_half(
                None,
                start_system,
                source_wp,
                [],
                max_to_buy,
                target_tradegood,
            )
            if not resp:
                time.sleep(SAFETY_PADDING)
                self.logger.error(
                    "Couldn't fetch any %s from %s, because %s",
                    target_tradegood,
                    ship.name,
                    resp.error,
                )
            resp = self.deliver_half(end_system, end_waypoint, target_tradegood)
        st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
        self.jettison_all_cargo([target_tradegood, return_tradegood])

        if return_tradegood and return_tradegood != "":
            resp = self.fetch_half(
                None,
                end_system,
                end_waypoint,
                [],
                max_to_buy,
                self.behaviour_params["return_tradegood"],
            )
            if resp:
                resp = self.deliver_half(start_system, source_wp, target_tradegood)
        self.end()

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

    def fetch_half(
        self,
        local_jumpgate,
        target_system: "System",
        target_waypoint: "Waypoint",
        path: list,
        max_to_buy: int,
        target_tradegood: str,
    ) -> LocalSpaceTradersRespose:
        ship = self.ship
        st = self.st
        if ship.nav.system_symbol != target_system.symbol:
            self.ship_intrasolar(local_jumpgate.symbol)
            self.ship_extrasolar(target_waypoint, path)
        self.ship_intrasolar(target_waypoint.symbol)

        st.ship_dock(ship)
        current_market = st.system_market(target_waypoint)
        if not current_market:
            self.logger.error(
                "No market found at waypoint %s", ship.nav.waypoint_symbol
            )
            time.sleep(SAFETY_PADDING)
            return current_market

        # empty anything that's not the goal.
        self.sell_all_cargo([target_tradegood], current_market)
        target_price = 1
        for listing in current_market.listings:
            if listing.symbol == target_tradegood:
                target_price = listing.purchase_price
                trade_volume = listing.trade_volume
                break

        space = ship.cargo_capacity - ship.cargo_units_used

        amount = min(
            space,
            max_to_buy,
            math.floor(self.agent.credits / target_price),
        )
        # do this X times where X is the amount to buy divided by the trade volume
        remaining_to_buy = amount
        for i in range(math.ceil(amount / trade_volume)):
            resp = st.ship_purchase_cargo(
                ship, target_tradegood, min(remaining_to_buy, trade_volume)
            )
            remaining_to_buy -= trade_volume
            if not resp:
                # couldn't buy anything.
                if resp.error_code in (
                    4604,
                    4600,
                ):  # our info about tradevolume is out of date
                    st.system_market(target_waypoint, True)

                self.logger.warning(
                    "Couldn't buy any %s, are we full? Is our market data out of date? Did we have enough money? I've done a refresh.  Manual intervention maybe required."
                )
                time.sleep(SAFETY_PADDING)
                return resp
        self.st.system_market(target_waypoint, True)
        return LocalSpaceTradersRespose(None, 0, None, url=f"{__name__}.fetch_half")

    def deliver_half(
        self, target_system, target_waypoint: "Waypoint", target_tradegood: str
    ):
        resp = self.ship_extrasolar(target_system)
        if not resp:
            return False
        resp = self.ship_intrasolar(target_waypoint)
        if not resp and resp.error_code != 4204:
            return False
        # now that we're here, decide what to do. Options are:
        # transfer (skip for now, throw in a warning)
        # fulfill
        # sell
        self.st.ship_dock(self.ship)
        if "fulfil_wp" in self.behaviour_params:
            resp = self.fulfil_any_relevant()
        elif "sell_wp" in self.behaviour_params:
            resp = self.sell_all_cargo()

        return resp


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    suffix = sys.argv[2] if len(sys.argv) > 2 else "1"
    ship = f"{agent}-{suffix}"
    bhvr = BuyAndDeliverOrSell_6(
        agent,
        ship,
        behaviour_params={
            "buy_wp": "X1-QV47-C42",
            "sell_wp": "X1-QV47-E47",
            "tradegood": "HYDROCARBON",
            "return_tradegood": "FUEL",
        },
    )
    lock_ship(ship, "MANUAL", bhvr.st.db_client.connection, duration=120)
    set_logging(logging.DEBUG)

    bhvr.run()
    lock_ship(ship, "MANUAL", bhvr.st.db_client.connection, duration=0)
