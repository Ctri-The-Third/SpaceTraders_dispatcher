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
    `fulfil_wp`: if you want the ship to deliver the cargo, set which waypoint\n
    `safety_profit_threshold`: if you want a safety cut out (15 minutes) if profits drop\n
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
        start_system = st.systems_view_one(ship.nav.system_symbol)
        safety_profit_margin = self.behaviour_params.get(
            "safety_profit_threshold", None
        )
        self.jettison_all_cargo([target_tradegood])

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
            source_market = st.system_market(source_wp)
            source_listing = source_market.get_tradegood(target_tradegood)
        if "sell_wp" in self.behaviour_params:
            end_system = st.systems_view_one(
                waypoint_slicer(self.behaviour_params["sell_wp"])
            )
            end_waypoint = st.waypoints_view_one(
                end_system.symbol, self.behaviour_params["sell_wp"]
            )
            end_market = st.system_market(end_waypoint)
            end_listing = end_market.get_tradegood(target_tradegood)
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

        #
        # if we've not been given specific instructions about where to sell, sell it at the best price, regardless of distance.
        #
        if not end_waypoint:
            potentials = self.find_best_market_systems_to_sell(target_tradegood)
            best_potench = potentials[0]
            best_cpd = 0
            for potench in potentials:
                waypoint_s, syst, sell_price = potench
                route = self.pathfinder.astar(start_system, syst)
                if route.jumps >= 0 and sell_price / min(route.jumps, 0.01) > best_cpd:
                    best_potench = potench
                    best_cpd = sell_price / min(route.jumps, 0.01)
            end_waypoint = st.waypoints_view_one(
                best_potench[1].symbol, best_potench[0]
            )
            end_system = best_potench[1]

        if "safety_profit_threshold" in self.behaviour_params:
            if source_listing and end_listing:
                projected_profit = (
                    end_listing.sell_price - source_listing.purchase_price
                )
                if projected_profit < safety_profit_margin:
                    self.logger.error(
                        "Safety profit margin not met for %s", target_tradegood
                    )

                    self.st.logging_client.log_custom_event(
                        "TRADER_SAFETY_MARGIN",
                        ship.name,
                        {
                            "tradegood": target_tradegood,
                            "margin": safety_profit_margin,
                            "profit": source_listing.sell_price
                            - end_listing.purchase_price,
                        },
                    )
                    self.end()

                    return

        if not target_waypoints:
            time.sleep(SAFETY_PADDING)
            self.logger.error("No waypoint found for tradegood %s", target_tradegood)
            raise ValueError("No waypoint found for tradegood %s" % target_tradegood)

        # vent any spare stuff before deploying.

        #
        # we know where we're going, we know what we're getting. Deployment.
        #

        # check the prices at the destination and the origin

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
        self.jettison_all_cargo([target_tradegood])
        st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
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
        #
        # this needs to validate that we're going to make a profit with current prices.
        # if we're not, sleep for 15 minutes, and return false. By the time it picks up, either the market goods will have shuffled (hopefully) or there'll be a new contract assigned.
        #
        ship = self.ship
        st = self.st
        current_market = st.system_market(target_waypoint)
        if ship.nav.system_symbol != target_system.symbol:
            self.ship_intrasolar(local_jumpgate.symbol)
            self.ship_extrasolar(target_waypoint, path)
        self.ship_intrasolar(target_waypoint.symbol, flight_mode="CRUISE")

        st.ship_dock(ship)
        if not current_market:
            self.logger.error(
                "No market found at waypoint %s", ship.nav.waypoint_symbol
            )
            time.sleep(SAFETY_PADDING)
            return current_market

        # empty anything that's not the goal.

        resp = self.purchase_what_you_can(
            target_tradegood, min(max_to_buy, ship.cargo_space_remaining)
        )
        if not resp:
            self.st.view_my_self(True)
            resp = self.purchase_what_you_can(
                target_tradegood, min(max_to_buy, ship.cargo_space_remaining)
            )
        if not resp:
            self.logger.error(
                "Couldn't purchase %s at %s, because %s",
                target_tradegood,
                ship.name,
                resp.error,
            )
            return resp
        return LocalSpaceTradersRespose(None, 0, None, url=f"{__name__}.fetch_half")

    def deliver_half(
        self, target_system, target_waypoint: "Waypoint", target_tradegood: str
    ):
        resp = self.ship_extrasolar(target_system)
        if not resp:
            return False
        resp = self.ship_intrasolar(target_waypoint, flight_mode="CRUISE")
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

    def check_traderoute_validity(
        self, origin_market: str, destination_market: str, tradegood: str
    ) -> bool:
        sql = """with pp as ( 
select purchase_price from market_tradegood_listings 
	where market_symbol = %s
	and trade_symbol = %s
select sell_price from market_tradegood_listings 
	where market_symbol = %s
	and trade_symbol = %s
	
	) 	
	select *, (sell_price - purchase_price) as profit_per_unit, (sell_price - purchase_price) > 0 as still_good  from pp join sp on true """
        results = try_execute_select(
            self.connection,
            sql,
            (
                origin_market,
                tradegood,
                destination_market,
                tradegood,
            ),
        )
        if results:
            return results[4]

        return False


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    suffix = sys.argv[2] if len(sys.argv) > 2 else "1"
    ship = f"{agent}-{suffix}"

    #        "X1-YG29-H50"	"X1-YG29-A3", 1 , "COPPER"

    params = {
        "buy_wp": "X1-YG29-J57",
        "sell_wp": "X1-YG29-H53",
        "priority": 4.5,
        "tradegood": "PRECIOUS_STONES",
        "safety_profit_threshold": 29.5,
    }
    bhvr = BuyAndDeliverOrSell_6(agent, ship, behaviour_params=params)
    lock_ship(ship, "MANUAL", bhvr.st.db_client.connection, duration=120)
    set_logging(logging.DEBUG)
    bhvr.st.view_my_self(True)
    bhvr.run()
    lock_ship(ship, "MANUAL", bhvr.st.db_client.connection, duration=0)
