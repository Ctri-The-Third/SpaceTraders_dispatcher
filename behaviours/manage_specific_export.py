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

BEHAVIOUR_NAME = "MANAGE_SPECIFIC_EXPORT"
SAFETY_PADDING = 60


class ManageSpecifcExport(Behaviour):
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
        self.target_tradegood = self.behaviour_params.get("target_tradegood")
        self.target_market = self.behaviour_params.get("market_wp", None)
        if self.target_market:
            self.starting_system = waypoint_slicer(self.target_market)
            self.starting_market_wp = self.st.waypoints_view_one(
                self.starting_system, self.target_market
            )
        else:
            self.starting_system = self.ship.nav.system_symbol
            self.starting_market_wp = self.ship.nav.waypoint_symbol
        self.markets = {}

    def run(self):
        self._run()
        self.end()

    def _run(self):
        super().run()
        st = self.st
        ship = self.ship
        agent = st.view_my_self()
        self.sleep_until_ready()
        st.logging_client.log_beginning(
            BEHAVIOUR_NAME,
            ship.name,
            agent.credits,
            behaviour_params=self.behaviour_params,
        )

        if not self.target_market:
            mkts = self.find_markets_that_export(self.target_tradegood)
            if len(mkts) == 0:
                return
            self.target_market = mkts[0]
            self.starting_system = waypoint_slicer(self.target_market)
            self.starting_market_wp = self.st.waypoints_view_one(
                self.starting_system, self.target_market
            )

        st.ship_cooldown(ship)

        # inspect the market and its tradegood
        # if data is old, go to it.

        market = self.get_market(self.target_market)
        export_wp = self.st.waypoints_view_one(
            waypoint_slicer(self.target_market), self.target_market
        )
        target_tradegood = market.get_tradegood(self.target_tradegood)
        if target_tradegood.recorded_ts < datetime.utcnow() - timedelta(hours=3):
            self.logger.debug(f"Market data is stale, going to {self.target_market}")
            self.ship_extrasolar(waypoint_slicer(self.target_market))
            self.ship_intrasolar(self.target_market)
            wp = self.st.waypoints_view_one(self.starting_system, self.target_market)
            market = self.st.system_market(wp, True)

        import_symbols = self.get_matching_imports_for_export(self.target_tradegood)
        worst_ratio = float("inf")
        for import_symbol in import_symbols:
            required_tradegood = market.get_tradegood(import_symbol)

            worst_ratio = min(
                worst_ratio,
                target_tradegood.trade_volume / required_tradegood.trade_volume,
            )

        # there are three criteria levels for exports - SCARCE supply, unRESTRICTED imports, and a supply ratio that is >= 3:1
        # Doesn't matter which we do, just so long as it's profitable.
        # currently the "maybe_sell_exports" doesn't factor in that ratio.
        # if we're in a circumstance where the two tradevolumes are equal, we need to prioritise imports so the TVs line up.
        #

        # calculate worst ratio
        # do imports if import state is not STRONG or RESTRICTED
        # if any ratio is < 3 and import procuring failed, do exports
        # if ratio is >= 3 do exports.
        succeeded = False
        resp = self.maybe_procure_imports(export_wp, market)
        # returns a list of tradegoods. We can then infer supply for each and target the scarcer of the two
        succeeded = resp if resp else succeeded

        if worst_ratio < 3 and not succeeded:
            resp = self.maybe_sell_exports()
            succeeded = resp if resp else succeeded
        elif worst_ratio >= 3:
            resp = self.maybe_sell_exports()
            succeeded = resp if resp else succeeded

        if not succeeded:
            self.logger.debug(
                f"Export for {target_tradegood.symbol} is {target_tradegood.supply}, activity is {target_tradegood.activity} - resting"
            )
            time.sleep(60)

            return

    def maybe_procure_imports(
        self,
        export_waypoint: "Waypoint",
        export_market: "Market",
        options: list[Market] = None,
    ):
        # find the markets that sell the desired tradegoods.
        # work out which is the most profitable in terms of CPH using travel time
        # buy the goods, then supply them to the manufactury
        import_symbols = self.get_matching_imports_for_export(self.target_tradegood)
        export_tg = export_market.get_tradegood(self.target_tradegood)

        success = False
        for required_import_symbol in import_symbols:
            import_listing = export_market.get_tradegood(required_import_symbol)
            # if this tradegood is in a STRONG state we don't need to do more to it except keep it strong
            # if it's restricted, we need to focus on exporting the export tradegood to free it up
            if import_listing.activity in ("STRONG", "RESTRICTED"):
                continue
            # now we know the imports that are needed - we need to go find them at a price that's profitable
            #
            # search for what we can buy
            #
            if not options:
                options = self.find_markets_that_export(required_import_symbol, False)
                options.extend(self.find_exchanges(required_import_symbol, False))
            markets = [self.get_market(m) for m in options]
            # exports are always gonna be more profitable than exports so lets go with profit-per-distance
            best_source_of_import = None
            best_cpd = 0
            for market in markets:
                required_good_export_tg = market.get_tradegood(required_import_symbol)
                if not required_good_export_tg:
                    continue
                wp = self.st.waypoints_view_one(
                    waypoint_slicer(market.symbol), market.symbol
                )
                distance = self.pathfinder.calc_travel_time_between_wps_with_fuel(
                    export_waypoint, wp, self.ship.fuel_capacity
                )
                # the difference between the purchase price of the fabricated export
                # and the raw goods. we want the biggest difference per distance
                # difference represents part of the value add from production
                cpd = (
                    export_tg.sell_price - required_good_export_tg.purchase_price
                ) / distance
                if cpd > best_cpd:
                    best_source_of_import = market
                    best_cpd = cpd

            if best_source_of_import:
                self.ship_extrasolar(waypoint_slicer(best_source_of_import.symbol))
                self.ship_intrasolar(best_source_of_import.symbol)
                self.buy_cargo(required_import_symbol, self.ship.cargo_space_remaining)
                self.ship_extrasolar(waypoint_slicer(export_market.symbol))
                self.ship_intrasolar(export_market.symbol)
                self.sell_all_cargo()
                success = True
                continue

            #
            # if we get here, there's no profitable exports matching our hungry imports
            # we should sweep for raw goods in extractors just in case.
            #
            packages = self.find_extractors_with_raw_goods(required_import_symbol)
            if not packages:
                self.logger.debug(
                    f"No profitable imports of {required_import_symbol} found! Resolve upstream supply issues. Sleeping for 60 seconds."
                )
                continue

            waypoint, raw_good, quantity = packages[0]
            self.ship_extrasolar(waypoint_slicer(waypoint))
            self.ship_intrasolar(waypoint)
            self.take_cargo_from_neighbouring_extractors(raw_good)
            self.ship_extrasolar(waypoint_slicer(export_market.symbol))
            self.ship_intrasolar(export_market.symbol)
            self.sell_all_cargo()
            success = True
        return success

    def maybe_sell_exports(self):
        # take the exports to the best CPH market.
        potential_markets = self.find_best_market_systems_to_sell(self.target_tradegood)
        waypoints = {
            m[0]: self.st.waypoints_view_one(waypoint_slicer(m[0]), m[0])
            for m in potential_markets
        }
        markets = [
            self.get_market(w.symbol)
            for w in waypoints.values()
            if w.system_symbol == self.starting_system
        ]
        export_tg = self.get_market(self.target_market).get_tradegood(
            self.target_tradegood
        )
        best_cph = 0
        best_sell_market = None
        for market in markets:
            wp = waypoints[market.symbol]
            distance = self.pathfinder.calc_travel_time_between_wps_with_fuel(
                self.starting_market_wp, wp, self.ship.fuel_capacity
            )
            profit = (
                market.get_tradegood(self.target_tradegood).sell_price
                - export_tg.purchase_price
            )
            cph = profit / distance
            if cph > best_cph:
                best_cph = cph
                best_sell_market = market

        if not best_sell_market and export_tg.activity == "WEAK":
            self.logger.debug(
                f"No profitable markets found, and we're not SCARCE yet - something's wrong downstream. "
            )
            time.sleep(60)
        if not best_sell_market:
            return False
        import_tg = best_sell_market.get_tradegood(self.target_tradegood)

        if export_tg.purchase_price >= import_tg.sell_price:
            return False

        self.ship_extrasolar(waypoint_slicer(self.target_market))
        self.ship_intrasolar(self.target_market)
        export_tg = self.get_market(self.target_market).get_tradegood(
            self.target_tradegood
        )
        export_tg = self.get_market(self.target_market).get_tradegood(
            self.target_tradegood
        )
        resp = self.buy_cargo(
            self.target_tradegood,
            min(
                export_tg.trade_volume,
                self.ship.cargo_space_remaining,
                math.floor(self.agent.credits / export_tg.purchase_price),
            ),
        )
        # self.buy_cargo(self.target_tradegood, self.ship.cargo_space_remaining)
        self.ship_extrasolar(waypoint_slicer(best_sell_market.symbol))
        self.ship_intrasolar(best_sell_market.symbol)
        self.sell_all_cargo()

        return True

    def find_markets_that_export(self, target_tradegood, highest_tradevolume=True):
        # find the market in the system with the highest tradevolume (or lowest)
        return self._find_markets_that_trade(
            target_tradegood, "EXPORT", highest_tradevolume
        )

    def find_exchanges(self, target_tradegood, highest_tradevolume=True):
        # find the market in the system with the highest tradevolume (or lowest)
        return self._find_markets_that_trade(
            target_tradegood, "EXCHANGE", highest_tradevolume
        )

    def find_markets_that_import(self, target_tradegood, highest_tradevolume=True):
        # find the market in the system with the highest tradevolume (or lowest)
        return self._find_markets_that_trade(
            target_tradegood, "IMPORT", highest_tradevolume
        )

    def _find_markets_that_trade(
        self, tradegood: str, listing_type: str, highest_tradevolume=True
    ):
        tg = tradegood
        waypoints = self.st.find_waypoints_by_trait(self.starting_system, "MARKETPLACE")
        markets = [self.get_market(w.symbol) for w in waypoints]
        markets = [
            m
            for m in markets
            if m.get_tradegood(tg) and m.get_tradegood(tg).type == listing_type
        ]

        markets = sorted(
            markets,
            key=lambda m: m.get_tradegood(tg).trade_volume,
            reverse=highest_tradevolume,
        )
        return [m.symbol for m in markets]

    def get_matching_imports_for_export(self, export_symbol: str):
        sql = """select import_tradegoods from manufacture_relationships
        where export_tradegood = %s"""
        rows = try_execute_select(self.connection, sql, (export_symbol,))
        if not rows:
            return []
        return rows[0][0]

    def find_extractors_with_raw_goods(self, raw_good: str):
        sql = """SELECT waypoint_Symbol, trade_symbol, sum(quantity)
FROM SHIP_CARGO sc 
join ship_nav sn on sc.ship_symbol = sn.ship_symbol
join ships s on sc.ship_symbol = s.ship_symbol
where ship_role = 'EXCAVATOR'
and trade_symbol = %s
group by 1,2 order by 3 desc """
        packages = try_execute_select(self.connection, sql, (raw_good,))
        if not packages:
            return []
        return packages

    def get_market(self, market_symbol: str) -> "Market":
        if market_symbol not in self.markets:
            wp = self.st.waypoints_view_one(
                waypoint_slicer(market_symbol), market_symbol
            )
            self.markets[market_symbol] = self.st.system_market(wp)
        return self.markets[market_symbol]

    def take_cargo_from_neighbouring_extractors(self, raw_good: str):
        neighbours = self.get_neighbouring_extractors()
        cargo_remaining = self.ship.cargo_space_remaining
        for neighbour in neighbours:
            neighbour: Ship
            for cargo_item in neighbour.cargo_inventory:
                if cargo_item.symbol == raw_good:
                    transfer_amount = min(cargo_item.units, cargo_remaining)
                    resp = self.st.ship_transfer_cargo(
                        neighbour, cargo_item.symbol, transfer_amount, self.ship.name
                    )
                    if resp:
                        cargo_remaining -= transfer_amount
                        if cargo_remaining == 0:
                            break


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "27"
    ship = f"{agent}-{ship_number}"
    behaviour_params = {
        "priority": 4.5,
        "target_tradegood": "EQUIPMENT",
        # "market_wp": "X1-YG29-D43",
    }

    bhvr = ManageSpecifcExport(agent, ship, behaviour_params or {})
    lock_ship(ship_number, "MANUAL", bhvr.st.db_client.connection, 60 * 24)
    for i in range(30):
        bhvr.run()
    lock_ship(ship_number, "MANUAL", bhvr.st.db_client.connection, 0)
