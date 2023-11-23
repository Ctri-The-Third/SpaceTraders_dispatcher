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
from straders_sdk.models import Market
from straders_sdk.utils import waypoint_slicer, set_logging, try_execute_select

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
        else:
            self.starting_system = self.ship.nav.system_symbol

    def run(self):
        self._run()
        self.end()

    def _run(self):
        super().run()
        st = self.st
        ship = self.ship
        agent = st.view_my_self()

        st.logging_client.log_beginning(BEHAVIOUR_NAME, ship.name, agent.credits)

        if not self.target_market:
            mkts = self.find_markets_that_export(self.target_tradegood)
            if len(mkts) == 0:
                return
            self.target_market = mkts[0]

        st.ship_cooldown(ship)

        # inspect the market and its tradegood
        # if data is old, go to it.
        # if the export market is RESTRICTED, find imports and BUY AND SELL
        # if the export market is ABUNDANT, HIGH, or MORDERATE, Sell to appropriate markets(prioritise imports)
        target_market_waypoint = st.waypoints_view_one(
            waypoint_slicer(self.target_market), self.target_market
        )
        market = st.system_market(target_market_waypoint)
        target_tradegood = market.get_tradegood(self.target_tradegood)
        if target_tradegood.recorded_ts < datetime.utcnow() - timedelta(hours=3):
            self.logger.info(f"Market data is stale, going to {self.target_market}")
            self.ship_extrasolar(waypoint_slicer(self.target_market))
            self.ship_intrasolar(self.target_market)
            return
        elif target_tradegood.activity == "RESTRICTED":
            self.logger.info(f"Market is RESTRICTED, finding imports")
            self.procure_imports()
            # returns a list of tradegoods. We can then infer supply for each and target the scarcer of the two

            return
        elif target_tradegood.supply not in ("ABUNDANT", "HIGH", "MODERATE"):
            self.logger.info(f"Market is {target_tradegood.supply}, finding imports")
            self.sell_exports()
            #
            return

    def procure_imports(self, export_market: "Market"):
        # find the markets that sell the desired tradegoods.
        # work out which is the most profitable in terms of CPH using travel time
        # buy the goods, then supply them to the manufactury
        import_symbols = self.get_matching_imports_for_export(self.target_tradegood)

        for symbol in import_symbols:
            # get the tradegood from the export market - find any that are SCARCE, then any that are LIMITED
            export_market.get_tradegood(symbol)
        pass

    def sell_exports(self):
        # take the exports to the best CPH market.
        pass

    def find_markets_that_export(self, highest_tradevolume=True):
        # find the market in the system with the highest tradevolume (or lowest)
        return self._find_markets_that_trade(
            self.target_tradegood, "EXPORT", highest_tradevolume
        )

    def find_markets_that_import(self, highest_tradevolume=True):
        # find the market in the system with the highest tradevolume (or lowest)
        return self._find_markets_that_trade(
            self.target_tradegood, "IMPORT", highest_tradevolume
        )

    def _find_markets_that_trade(
        self, tradegood: str, listing_type: str, highest_tradevolume=True
    ):
        tg = tradegood
        waypoints = self.st.find_waypoints_by_trait(self.starting_system, "MARKETPLACE")
        markets = [self.st.system_market(w) for w in waypoints]
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
        return rows[0]


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "1"
    ship = f"{agent}-{ship_number}"
    behaviour_params = {
        "priority": 4.5,
        "target_tradegood": "ADVANCED_CIRCUITRY",
        "market_wp": "X1-YG29-D43",
    }
    bhvr = ManageSpecifcExport(agent, ship, behaviour_params or {})
    lock_ship(ship_number, "MANUAL", bhvr.st.db_client.connection, 60 * 24)
    bhvr.run()
    lock_ship(ship_number, "MANUAL", bhvr.st.db_client.connection, 0)
