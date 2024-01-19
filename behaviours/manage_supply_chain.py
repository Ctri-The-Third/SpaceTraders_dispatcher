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

BEHAVIOUR_NAME = "MAINTAIN_SUPPLY_CHAIN"
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
        self.target_tradegood = self.behaviour_params.get("target_tradegood", None)
        self.chain = None
        self.max_import_tv = self.behaviour_params.get("max_tv", 180)
        self.max_export_tv = math.floor(self.max_import_tv * (2 / 3))
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

        next_link = self.select_deepest_restricted_trade(self.chain)

        if next_link:
            next_good = next_link.export_symbol
            sell_wp_s = next_link.market_symbol

            sell_market = self.get_market(sell_wp_s)
            best_market = self.get_market(sell_wp_s)
            best_cost = float("inf")
            if len(next_link.import_symbols) > 0:
                for item in next_link.import_symbols:
                    tg = sell_market.get_tradegood(item)
                    if SUPPLY_LEVELS[tg.supply] == 1:
                        markets = self.find_markets_that_trade(
                            item, self.ship.nav.system_symbol
                        )
                        for market in markets:
                            tg = market.get_tradegood(item)
                            if tg is None:
                                continue
                            if tg.type in ("EXPORT", "EXCHANGE"):
                                if tg.purchase_price < best_cost:
                                    best_market = market
                                    best_cost = tg.purchase_price
                                    next_good = item
            if not best_market:
                self.logger.info("No unrestricted trades found")
                self.st.sleep(SAFETY_PADDING)
            buy_wp_s = best_market.symbol
        if not next_link:
            # next_link = self.search_deeper_for_under_evolved_export(self.chain)
            if next_link:
                next_link: ChainLink

                next_good = next_link.export_symbol
                buy_wp_s = next_link.market_symbol
                sell_wp_s = self.find_import_market_for_export_from_chain(
                    self.chain, next_link.export_symbol, buy_wp_s
                )
            # currently this returns the buy link, not the import link.

        if not next_link:
            next_link = self.search_deeper_for_abundant_export(self.chain)
            if next_link:
                next_good = next_link.export_symbol
                buy_wp_s = next_link.market_symbol
                sell_wp_s = self.find_import_market_for_export_from_chain(
                    self.chain, next_link.export_symbol, buy_wp_s
                )
        # for the export market, we need to find its imports. for its imports we need to find ANY source, and supply.
        # next_good, sell_wp_s = self.find_export_from_import(self.chain, next_good)
        first_market = True
        last_run = False
        did_something = False
        while (next_link and next_good and sell_wp_s) or (last_run and sell_wp_s):
            buy_system = st.systems_view_one(waypoint_slicer(buy_wp_s))
            buy_wp = st.waypoints_view_one(buy_wp_s)
            sell_sys = st.systems_view_one(waypoint_slicer(sell_wp_s))
            sell_wp = st.waypoints_view_one(sell_wp_s)
            buy_market_tg = self.get_market(buy_wp_s).get_tradegood(next_good)
            sell_market_tg = self.get_market(sell_wp_s).get_tradegood(next_good)

            print(
                f"we're going from {buy_wp_s} to {sell_wp_s} for {next_good} - which is useful for {next_link}"
            )
            # only execute this link if it's going to be profitable. any profit is fine.
            # actually no - our goal is evolution, so we can make a degree of loss to push the first / focus market into a better state.
            # If we have to push a supply market quite deep into unprofitability to get it to evolve, that's okay :)
            # first unrestrict all markets
            # then
            if first_market or buy_market_tg.purchase_price < sell_market_tg.sell_price:
                if not next_good in [x.symbol for x in ship.cargo_inventory]:
                    self.go_and_buy(
                        next_good, buy_wp, max_to_buy=self.ship.cargo_capacity
                    )
                self.go_and_sell_or_fulfill(next_good, sell_wp)
                first_market = False
                did_something = True

            # J62 -> 55

            # our current approach assumes an import only gets used once - but if we're importing silicon crystals for microprocessors and electronics - how will it pick the correct next step?
            # we need to get multiple answers from this.
            # the issue here is because the chain links only have children, not parents so we can't direct refer up the way.
            # how would we add this? probably with a "from" array.

            # our current link is copper - our next good needs to be the export of the current link
            if not next_link:
                break
            next_good = next_link.export_symbol

            buy_wp_s = sell_wp_s
            if not next_link.parent_link and not last_run:
                sell_wp_s = self.find_import_market_in_system(next_good)
                next_link = next_link.parent_link
                last_run = True
            elif last_run:
                next_link = None
            else:
                next_link = next_link.parent_link
                sell_wp_s = next_link.market_symbol

        if not did_something:
            self.logger.info("No unrestricted, unevolved trades found")
            self.st.sleep(SAFETY_PADDING)

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
        return self.search_deeper_for_restricted(chain, best_depth=0, came_from={})

    def search_deeper_for_restricted(
        self, chain: "ChainLink", best_depth=0, restricted_good=None, came_from={}
    ) -> "ChainLink":
        "returns a tuple of (trade_symbol, market_symbol)"
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
                # we check for import symbols for situations where we have a market that exports something (e.g. COPPER_ORE) but we've deliberately hidden the imports (e.g. EXPLOSIVES)
                and len(chain.import_symbols) > 0
            ):
                restricted_good = chain

                break
            else:
                pass
        if chain.import_links:
            for link in chain.import_links:
                restricted_good = self.search_deeper_for_restricted(
                    link, best_depth + 1, restricted_good
                )

        return restricted_good

    def search_deeper_for_under_evolved_export(self, chain: "ChainLink", best_depth=0):
        # if all markets are now unrestricted, then we need to check that exports aren't sitting in the ABUNDANT (>80% of maximum price) range, and bring them down to High or Moderate

        for link in chain.import_links:
            next_link = self.search_deeper_for_under_evolved_export(
                link, best_depth + 1
            )
            if next_link:
                return next_link
        if chain.market_symbol:
            export = self.get_market(chain.market_symbol).get_tradegood(
                chain.export_symbol
            )
        else:
            mkts = self.find_markets_that_trade(
                chain.export_symbol, self.ship.nav.system_symbol
            )
            best_mkt = None
            for mkt in mkts:
                mkt: Market
                tg = mkt.get_tradegood(chain.export_symbol)
                if not tg:
                    continue
                if (
                    not best_mkt
                    or tg.purchase_price
                    < best_mkt.get_tradegood(chain.export_symbol).purchase_price
                ):
                    best_mkt = mkt
            export = best_mkt.get_tradegood(chain.export_symbol)
        if export.trade_volume < self.max_export_tv and export.type == "EXPORT":
            import_market_symbol = self.find_import_market_in_system(
                chain.export_symbol
            )
            import_market = self.get_market(import_market_symbol)
            import_tg = import_market.get_tradegood(chain.export_symbol)
            if import_tg and SUPPLY_LEVELS[import_tg.supply] > 1:
                return chain

    def search_deeper_for_abundant_export(self, chain: "ChainLink", best_depth=0):
        # if all markets are now unrestricted, then we need to check that exports aren't sitting in the ABUNDANT (>80% of maximum price) range, and bring them down to High or Moderate
        if not chain or not chain.market_symbol:
            return
        export = self.get_market(chain.market_symbol).get_tradegood(chain.export_symbol)

        for link in chain.import_links:
            chain = self.search_deeper_for_abundant_export(link, best_depth + 1)
            if chain:
                return chain
        if SUPPLY_LEVELS[export.supply] == 5 and export.type == "EXPORT":
            import_market_symbol = self.find_import_market_in_system(export.symbol)
            # if there's no import market, then we it's not a valid abundant export.
            # for things like FAB_MATS, and the super advanced goods in a system.
            if not import_market_symbol:
                return
            import_market = self.get_market(import_market_symbol)
            import_tg = import_market.get_tradegood(export.symbol)
            if (
                import_tg
                and SUPPLY_LEVELS[import_tg.supply] > 1
                and export.purchase_price < import_tg.purchase_price
            ):
                return chain

    def find_import_market_for_export_from_chain(
        self, chain: "ChainLink", target_good: str, source_market
    ) -> str:
        # starting at the top of the chain, recurse down it until you find the target good being exported, and consumed by something else.

        if target_good == chain.export_symbol and chain.market_symbol == source_market:
            if chain.parent_link:
                return chain.parent_link.market_symbol
            else:
                return None
        for link in chain.import_links:
            mkt = self.find_import_market_for_export_from_chain(
                link, target_good, source_market
            )
            if mkt:
                return mkt

    def find_import_market_in_system(self, target_good) -> str:
        possibilities = []
        for market in self.markets.values():
            market: Market
            tg = market.get_tradegood(target_good)
            if tg and tg.type == "IMPORT":
                possibilities.append(market)

        if len(possibilities) == 0:
            sql = """select market_symbol from market_Tradegood_listings mtl 
    where market_symbol ilike %s
    and trade_symbol = %s
    and type = 'IMPORT'"""
            results = try_execute_select(
                sql, (f"{self.ship.nav.system_symbol}%", target_good)
            )
            for result in results:
                possibilities.append(self.get_market(result[0]))

        best_possibility = None
        best_price = float("inf")
        for possibility in possibilities:
            possibility: Market
            tg = possibility.get_tradegood(target_good)
            if tg and tg.purchase_price < best_price:
                best_possibility = possibility
                best_price = tg.purchase_price
        return best_possibility.symbol if best_possibility else None

    def next_link_up(self, chain: "ChainLink", import_good: str, market_symbol: str):
        # starting at the top - we've a link.
        # if the import_good is in the import_symbols, the export market is the import market.

        if import_good in chain.import_symbols:
            return chain
        for link in chain.import_links:
            mkt = self.next_link_up(link, import_good, market_symbol)
            if mkt:
                return mkt

    def select_most_profitable_line(self):
        pass

    def find_export_from_import(self, chain: "ChainLink", target_good: str) -> str:
        # we need to go down the chain until we find a restricted import - then go the rest of the way down that chain and start from there
        # we should find the deepest restricted import, and trade it.
        return self.search_deeper_for_import(chain, target_good)

    def search_deeper_for_export(
        self, chain: "ChainLink", target_good: str, buy_wp_s: str
    ) -> str:
        # starting at the top of the chain, recurse down it until you find the target good being exported, and consumed by something else.
        if chain.export_symbol == target_good and chain.market_symbol == buy_wp_s:
            return chain
        for link in chain.import_links:
            found_link = self.search_deeper_for_export(link, target_good, buy_wp_s)
            if found_link:
                return found_link

        return (None, None)

    def search_deeper_for_import(self, chain: "ChainLink", target_good: str) -> str:
        if target_good in chain.import_symbols:
            return (chain.export_symbol, chain.market_symbol)
        for link in chain.import_links:
            mkt = self.search_deeper_for_import(link, target_good)
            if mkt:
                return mkt
        return (None, None)

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
        self,
        relationships: dict,
        export_being_inspected,
        depth=0,
        all_symbols=[],
        parent_link=None,
    ) -> "ChainLink":
        # chain is the current node
        # but if we pass the current node all the way down to the bottom, we don't get a tree
        # so inst
        trading_markets = self.find_markets_that_trade(
            export_being_inspected, self.ship.nav.system_symbol
        )
        market_export_location = None
        for market in trading_markets:
            market: Market
            tg = market.get_tradegood(export_being_inspected)
            if tg.type == "EXPORT":
                market_export_location = market.symbol
                break

        chain = ChainLink(
            export_being_inspected,
            relationships.get(export_being_inspected, []),
            depth=depth,
            market_symbol=market_export_location,
            parent_link=parent_link,
        )
        all_symbols.append(export_being_inspected)
        if export_being_inspected in relationships:
            imports_being_inspected = relationships[export_being_inspected]
            for import_being_inspected in imports_being_inspected:
                chain.all_symbols = all_symbols
                chain.import_links.append(
                    self._recurse_chain(
                        relationships,
                        import_being_inspected,
                        depth + 1,
                        parent_link=chain,
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
        market_symbol: str = None,
        depth=0,
        parent_link: "ChainLink" = None,
    ) -> None:
        if not import_links:
            import_links = []
        self.export_symbol = export_symbol
        self.import_symbols = import_symbols
        self.import_links = import_links
        self.depth = depth
        self.all_symbols = all_symbols or []
        self.market_symbol = market_symbol
        self.parent_link = parent_link

    def __repr__(self) -> str:
        return f"ChainLink({self.export_symbol} <- {self.import_symbols}  [{self.depth}]@{self.market_symbol})"


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
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "11"
    ship = f"{agent}-{ship_number}"
    behaviour_params = {
        "priority": 3,
        "target_tradegood": "CLOTHING",
    }

    while True:
        bhvr = ManageManufactureChain(agent, ship, behaviour_params or {})

        lock_ship(ship, "MANUAL", 60 * 24)

        bhvr.run()
    lock_ship(ship, "MANUAL", 0)
