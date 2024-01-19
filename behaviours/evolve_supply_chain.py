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

BEHAVIOUR_NAME = "EVOLVE_SUPPLY_CHAIN"
SAFETY_PADDING = 180


class EvolveSupplyChain(Behaviour):
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
        self.target_tradegoods = self.behaviour_params.get("target_tradegoods", None)
        self.chain = None
        self.max_tv = self.behaviour_params.get("max_tv", 180)
        self.max_export_tv = math.floor(self.max_tv * (2 / 3))
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

        target_tradegoods = self.target_tradegoods
        had_to_do_something = False
        for target_tradegood in target_tradegoods:
            self.chain = self.populate_chain(target_tradegood)

            target_link = self.search_deeper_for_under_evolved_export(self.chain)
            if not target_link:
                continue
            max_import_tv = math.floor(
                self.max_tv * ((2 / 3) ** target_link.import_height)
            )
            max_export_tv = math.floor(max_import_tv * (2 / 3))
            # for each import, check the supply level. If it's 3, then we need to fill it to abundant.
            # then for the export, check the supply level - if it's 3 then we need to drain it to scarce.
            main_market = self.get_market(target_link.market_symbol)
            main_waypoint = self.st.waypoints_view_one(target_link.market_symbol)
            for i in target_link.import_symbols:
                tg = main_market.get_tradegood(i)
                if (
                    tg
                    and tg.trade_volume < max_import_tv
                    and SUPPLY_LEVELS[tg.supply] <= 4
                ):
                    while (
                        SUPPLY_LEVELS[tg.supply] < 5
                        and not self.termination_event.is_set()
                    ):
                        possible_sources = self.find_markets_that_trade(
                            i, self.ship.nav.system_symbol
                        )
                        possible_market_symbols = [m.symbol for m in possible_sources]
                        purchase_waypoint = self.pick_nearest_profitable_market_to_buy(
                            possible_market_symbols,
                            main_waypoint,
                            tg.symbol,
                            tg.sell_price,
                        )
                        if not purchase_waypoint:
                            self.logger.warning(
                                "Can't find a profitable export of %s to fill import!! Evolution cannot continue.",
                                i,
                            )
                            break
                        had_to_do_something = True

                        purchase_waypoint = self.st.waypoints_view_one(
                            purchase_waypoint
                        )
                        # source market = closest profitable market that sells the import
                        resp = self.go_and_buy(i, purchase_waypoint)
                        if not resp:
                            st.sleep(SAFETY_PADDING)
                            break
                        resp = self.go_and_sell_or_fulfill(i, main_waypoint)
                        if not resp:
                            st.sleep(SAFETY_PADDING)
                            break
                        # this refreshed market is still giving "moderate" - something not quite right here.
                        main_market = self.get_market(target_link.market_symbol, True)
                        tg = main_market.get_tradegood(i)

            tg = main_market.get_tradegood(target_link.export_symbol)
            if tg and tg.trade_volume < max_export_tv and SUPPLY_LEVELS[tg.supply] >= 2:
                while (
                    SUPPLY_LEVELS[tg.supply] > 1 and not self.termination_event.is_set()
                ):
                    if target_link.parent_link:
                        possible_destination = target_link.parent_link.market_symbol
                    else:
                        # needs trimmed
                        possible_destinations = self.find_best_market_systems_to_sell(
                            target_link.export_symbol
                        )
                        possible_market_symbols = [m[0] for m in possible_destinations]
                        possible_destination = (
                            self.pick_nearest_profitable_market_to_buy(
                                possible_market_symbols,
                                main_waypoint,
                                tg.symbol,
                                tg.purchase_price,
                            )
                        )
                    if not possible_destination:
                        self.logger.warning(
                            "Can't find a profitable import of %s to drain export!! Evolution cannot continue.",
                            target_link.export_symbol,
                        )
                        break
                    had_to_do_something = True

                    # source market = closest profitable market that sells the import
                    resp = self.go_and_buy(
                        target_link.export_symbol,
                        st.waypoints_view_one(target_link.market_symbol),
                    )
                    if not resp:
                        self.st.sleep(SAFETY_PADDING)
                        break

                    resp = self.go_and_sell_or_fulfill(
                        target_link.export_symbol,
                        st.waypoints_view_one(possible_destination),
                    )
                    if not resp:
                        self.st.sleep(SAFETY_PADDING)
                        break
                    main_market = self.get_market(target_link.market_symbol, True)
                    tg = main_market.get_tradegood(target_link.export_symbol)
        if not had_to_do_something:
            # if we're here, all actions have been completed and we can rest as this step needs to percolate and evolve before it's done.
            #
            self.log_market_changes(main_market.symbol)
            st.sleep(SAFETY_PADDING)
            return

        # find the best markt that sells the necessary import

    def pick_nearest_profitable_market_to_buy(
        self,
        markets: list[tuple],
        comparrison_waypoint: Waypoint,
        target_tradegood,
        target_sell_price,
    ):
        best_waypoint = None
        best_distance = float("inf")
        for market_s in markets:
            market = self.get_market(market_s)
            tg = market.get_tradegood(target_tradegood)

            waypoint = self.st.waypoints_view_one(market.symbol)
            distance = self.pathfinder.calc_distance_between(
                comparrison_waypoint, waypoint
            )
            if tg.purchase_price < target_sell_price and distance < best_distance:
                best_waypoint = waypoint.symbol
                best_distance = distance
        return best_waypoint

    def pick_nearest_profitable_market_to_sell(
        self,
        markets: list[tuple],
        comparrison_waypoint: Waypoint,
        target_tradegood,
        target_buy_price,
    ):
        best_waypoint = None
        best_distance = float("inf")
        for market_s in markets:
            market = self.get_market(market_s)
            tg = market.get_tradegood(target_tradegood)

            waypoint = self.st.waypoints_view_one(market.symbol)
            distance = self.pathfinder.calc_distance_between(
                comparrison_waypoint, waypoint
            )
            if tg.sell_price > target_buy_price and distance < best_distance:
                best_waypoint = waypoint.symbol
                best_distance = distance
        return best_waypoint

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

    def search_deeper_for_under_evolved_export(
        self, chain: "ChainLink", best_height=float("inf")
    ):
        # if all markets are now unrestricted, then we need to check that exports aren't sitting in the ABUNDANT (>80% of maximum price) range, and bring them down to High or Moderate

        for link in chain.import_links:
            next_link = self.search_deeper_for_under_evolved_export(link, best_height)
            if next_link:
                return next_link
        if not chain.import_symbols:
            return

        if chain.import_height < best_height:
            market = self.get_market(chain.market_symbol)
            tg = market.get_tradegood(chain.export_symbol)
            import_max_tv = math.floor(self.max_tv * ((2 / 3) ** chain.import_height))
            export_max_tv = math.floor(import_max_tv * (2 / 3))
            if tg and tg.trade_volume < export_max_tv:
                return chain

            for symbol in chain.import_symbols:
                tg = market.get_tradegood(symbol)

                # it's actually okay if imports DEvolve their TV, so long as it's at least equal to the import.
                # 1:1 ratio is actually ideal (instead of 3:2) since it saves on time spend fueling lower stages of the process.
                if tg and tg.trade_volume < export_max_tv:
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

    def get_market(self, market_symbol: str, refresh=False) -> Market:
        if market_symbol in self.markets and not refresh:
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
        chain = self._add_heights_to_chain(chain)
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

    def _add_heights_to_chain(self, chain: "ChainLink") -> "ChainLink":
        if chain.import_links:
            for link in chain.import_links:
                link = self._add_heights_to_chain(link)
                if link.import_height >= chain.import_height:
                    chain.import_height = link.import_height + 1
        else:
            chain.import_height = -1
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
        self.import_height = 0

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
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "1A"
    ship = f"{agent}-{ship_number}"
    behaviour_params = {
        "priority": 4,
        "script_name": "EVOLVE_SUPPLY_CHAIN",
        "target_tradegoods": ["CLOTHING", "FOOD", "MEDICINE", "FUEL"],
    }
    while True:
        bhvr = EvolveSupplyChain(agent, ship, behaviour_params or {})

        lock_ship(ship, "MANUAL", 60 * 24)

        bhvr.run()
    lock_ship(ship, "MANUAL", 0)
