# the goal is filling the imports so things aren't restricted.
# recurse down tree until find a suitable node e.g.
# clothing -> fabrics -> fertilizers -> liquid_nitrogen

# If clothing is restricted, look at fabrics.
# if Fabrics are restricted, look at fertilizers.
# if fertilizers are restricted, look at liquid nitrogen, which is a raw good
# bring raw goods to fertilizers, repeat.


# takes a tradegood. Then trades that to ensure that the market is LIMITED
# if the export activity hits RESTRICTED, it switches to finding profitable import goods until that clears.

# script is happy to work to 0 profit, but will not work at a loss.


import time
import sys
from dataclasses import dataclass


sys.path.append(".")
from behaviours.generic_behaviour import Behaviour
import logging

from datetime import datetime, timedelta
from straders_sdk.client_api import SpaceTradersApiClient as SpaceTraders
from straders_sdk.ship import Ship
from straders_sdk.models import Market, Waypoint
from straders_sdk.utils import waypoint_slicer, set_logging, try_execute_select
from straders_sdk.constants import SUPPLY_LEVELS, MANUFACTURED_BY
import math
from behaviours.generic_behaviour import Behaviour

BEHAVIOUR_NAME = "CHAIN_TRADES"
SAFETY_PADDING = 180


class ManageManufactureChain(Behaviour):
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
        self.target_tradegood = self.behaviour_params.get("tradegood", None)
        self.chain = None
        self.markets = {}
        self.tg_s_markets = {}

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
        self.chain = self.populate_chain(self.target_tradegood)

        target_good = self.select_deepest_restricted_trade(self.chain)

        params = {}
        if not params:
            params = self.select_deepest_restricted_trade()
        if not params:
            params = select_most_profitable_line()
        if not params:
            self.logger.info("No trades found")
            time.sleep(SAFETY_PADDING)

        buy_system = st.systems_view_one(waypoint_slicer(params["buy_wp"]))
        buy_wp = st.waypoints_view_one(params["buy_wp"])
        sell_sys = st.systems_view_one(waypoint_slicer(params["sell_wp"]))
        sell_wp = st.waypoints_view_one(params["sell_wp"])
        tradegood = params["tradegood"]
        pass
        if not tradegood in [x.symbol for x in ship.cargo_inventory]:
            self.go_and_buy(tradegood, buy_wp, max_to_buy=self.ship.cargo_capacity)

        self.go_and_sell_or_fulfill(tradegood, sell_wp)

    def select_positive_trade(self):
        # this gets all viable trades for a given system
        # it lists all the trades from the current market first, then all others afterwards#
        # it will then go by the most profitable (profit per distance).

        sql = """
    SELECT route_value, system_symbol, trade_symbol, profit_per_unit, export_market, export_x, export_y, purchase_price, sell_price, supply_value,  supply_text, import_supply, market_depth, import_market, import_x, import_y, distance, export_activity
	FROM public.trade_routes_intrasystem
    where system_symbol = %s
    and purchase_price < %s
    and ((supply_value >= 4 and export_activity = 'STRONG') or supply_value >= 3)
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
            return {}
        best_result = TradeRoute(*results[0])
        params = {
            "tradegood": best_result.trade_symbol,
            "buy_wp": best_result.export_market,
            "sell_wp": best_result.import_market,
            "quantity": self.ship.cargo_capacity,
            # half of sellprice - buyprice
            "safety_profit_threshold": (
                best_result.sell_price - best_result.purchase_price
            )
            / 2,
        }
        return params

    def select_deepest_restricted_trade(self, chain, best_result=None) -> str:
        # we need to go down the chain until we find a restricted import - then go the rest of the way down that chain and start from there
        # we should find the deepest restricted import, and trade it.
        return self.search_deeper_for_restricted(chain, best_depth=0)

    def search_deeper_for_restricted(
        self, chain: "ChainLink", best_depth=0, restricted_good=""
    ) -> "str":
        mkts = self.find_markets_that_trade(
            chain.export_symbol, self.ship.nav.system_symbol
        )
        for mkt in mkts:
            mkt: Market
            tg = mkt.get_tradegood(chain.export_symbol)
            if not tg:
                continue
            if (
                tg.type == "EXPORT"
                and tg.activity == "RESTRICTED"
                and chain.depth >= best_depth
            ):
                restricted_good = tg.symbol

                break
        if chain.import_links:
            for link in chain.import_links:
                restricted_good = self.search_deeper_for_restricted(
                    link, best_depth + 1, restricted_good
                )

        return restricted_good

    def get_market(self, market_symbol: str) -> Market:
        if market_symbol in self.markets:
            return self.markets[market_symbol]
        wp = self.st.waypoints_view_one(market_symbol)
        market = self.st.system_market(wp)
        self.markets[market_symbol] = market
        return market

    def find_markets_that_trade(self, tradegood: str, system_symbol: str):
        if tradegood not in self.tg_s_markets:
            wayps = self.st.find_waypoints_by_trait(system_symbol, "MARKETPLACE")
            mkts = [self.st.system_market(w) for w in wayps]
            for mkt in mkts:
                for tg in mkt.listings:
                    if tg.symbol not in self.tg_s_markets:
                        self.tg_s_markets[tg.symbol] = []
                    self.tg_s_markets[tg.symbol].append(mkt)
        return self.tg_s_markets.get(tradegood, [])

    def populate_chain(
        self,
        top_level: str,
    ) -> "ChainLink":
        # this gets all viable trades for a given system
        # it lists all the trades from the current market first, then all others afterwards#
        # it will then go by the most profitable (profit per distance).

        relationships = MANUFACTURED_BY
        chain = self._recurse_chain(relationships, top_level, all_symbols=[top_level])
        return chain

    def _recurse_chain(
        self, relationships: dict, export_being_inspected, depth=0, all_symbols=[]
    ) -> "ChainLink":
        # chain is the current node
        # but if we pass the current node all the way down to the bottom, we don't get a tree
        # so inst
        chain = ChainLink(
            export_being_inspected,
            relationships.get(export_being_inspected, []),
            depth=depth,
        )
        all_symbols.append(export_being_inspected)
        if export_being_inspected in relationships:
            imports_being_inspected = relationships[export_being_inspected]
            for import_being_inspected in imports_being_inspected:
                chain.all_symbols = all_symbols
                chain.import_links.append(
                    self._recurse_chain(
                        relationships, import_being_inspected, depth + 1
                    )
                )

        return chain


class ChainLink:
    def __init__(
        self,
        export_symbol: str,
        import_symbols: list[str],
        import_links: list["ChainLink"] = None,
        all_symbols: list[str] = None,
        depth=0,
    ) -> None:
        if not import_links:
            import_links = []
        self.export_symbol = export_symbol
        self.import_symbols = import_symbols
        self.import_links = import_links
        self.depth = depth
        self.all_symbols = all_symbols or []

    def __repr__(self) -> str:
        return (
            f"ChainLink({self.export_symbol} <- {self.import_symbols}  [{self.depth}])"
        )


@dataclass
class TradeRoute:
    #    SELECT route_value, system_symbol, trade_symbol, profit_per_unit, export_market, export_x, export_y, purchase_price, sell_price, supply_value,  supply_text, import_supply, market_depth, import_market, import_x, import_y, distance, export_activity
    route_value: float
    system_symbol: str
    trade_symbol: str
    profit_per_unit: float
    export_market: str
    export_x: int
    export_y: int
    purchase_price: float
    sell_price: float
    supply_value: int
    supply_text: str
    import_supply: int
    market_depth: int
    import_market: str
    import_x: int
    import_y: int
    distance: float
    export_activity: str


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "18"
    ship = f"{agent}-{ship_number}"
    behaviour_params = {
        "priority": 3,
        "tradegood": "FAB_MATS",
    }

    bhvr = ManageManufactureChain(agent, ship, behaviour_params or {})

    lock_ship(ship, "MANUAL", bhvr.st.db_client.connection, 60 * 24)

    bhvr.run()
    lock_ship(ship, "MANUAL", bhvr.st.db_client.connection, 0)
