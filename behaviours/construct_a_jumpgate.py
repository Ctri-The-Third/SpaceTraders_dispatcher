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

BEHAVIOUR_NAME = "CONSTRUCT_JUMPGATE"
SAFETY_PADDING = 180


class ConstructJumpgate(Behaviour):
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

        self.logger = logging.getLogger(BEHAVIOUR_NAME)
        self.target_waypoint = self.behaviour_params.get("target_wp", None)
        self.source_markets = self.behaviour_params.get("market_wps", [])

        self.markets = {}

    def run(self):
        super().run()
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
        ship = self.ship
        agent = st.view_my_self()

        if not self.target_waypoint:
            wayp = st.find_waypoints_by_type_one(
                waypoint_slicer(self.agent.headquarters), "JUMP_GATE"
            )
            if wayp:
                self.target_waypoint = wayp.symbol
            else:
                self.logger.error("No jumpgate found")
                self.st.sleep(SAFETY_PADDING)
                return

        jumpgate = st.waypoints_view_one(self.target_waypoint, True)
        if jumpgate.type != "JUMP_GATE":
            self.st.sleep(SAFETY_PADDING)
            self.logger.error("Target waypoint is not a jumpgate")
            self.end("Target waypoint is not a jumpgate")

        if not jumpgate.under_construction:
            self.st.sleep(SAFETY_PADDING)
            self.logger.error("Target waypoint is complete!")
            self.end("Target waypoint is complete!")

        j_construction_site = st.system_construction(jumpgate)
        if not j_construction_site:
            self.st.sleep(SAFETY_PADDING)
            self.logger.error("Target waypoint has no construction site!")
            self.end("Target waypoint has no construction site!")

        requirements = [
            m for m in j_construction_site.materials if m.fulfilled < m.required
        ]

        for r in requirements:
            markets = self.source_markets or self.find_markets_that_export(
                r.symbol, highest_tradevolume=True
            )
            for market in markets:
                wp = st.waypoints_view_one(market)
                mkt = st.system_market(wp)
                # if we're specifying markets, they won't all sell all the exports.
                tg = mkt.get_tradegood(r.symbol)
                if not tg:
                    continue
                if SUPPLY_LEVELS[tg.supply] >= 3:
                    self.go_fetch_something(
                        r.symbol, wp, jumpgate, r.required - r.fulfilled
                    )

        # ✅ step 1 - assess if any work needs doing
        ## ✅ waypoint model needs an "isUnderConstruction"
        ## ✅ waypoint model needs a modifiers array
        ## ✅n eed a "get construction site endpoint"
        ### ✅ need a construction site model
        # ✅ step 2 - if so, find markets that sell the tradegood
        # ✅ step 3 - filter markets to those that are in-system
        # step 4 - buy the tradegood and take it to the construction site
        # step 5 - use the tradegood for construction

    def go_fetch_something(
        self, tradegood: str, buy_wp: Waypoint, build_wp: Waypoint, quantity: int
    ):
        have_cargo_already = False
        for inv in self.ship.cargo_inventory:
            if inv.symbol == tradegood and inv.units >= min(
                quantity, self.ship.cargo_capacity
            ):
                have_cargo_already = True
                break

        if not have_cargo_already:
            target_tg = self.get_market(buy_wp.symbol).get_tradegood(tradegood)
            if target_tg:
                # we want to ensure there's at least double what we're buying in the bank afterwards.
                available_credits = (
                    self.agent.credits
                    - (target_tg.purchase_price * target_tg.trade_volume) * 2
                )
                quantity = min(
                    available_credits // target_tg.purchase_price,
                    target_tg.trade_volume,
                )
                if quantity <= 0:
                    self.logger.warning(
                        "Not enough credits to safely buy anything - sleeping"
                    )
                    self.st.sleep(SAFETY_PADDING)
                    return
            self.ship_extrasolar_jump(waypoint_slicer(buy_wp.symbol))
            self.ship_intrasolar(buy_wp.symbol)
            self.buy_cargo(tradegood, quantity)
        self.ship_extrasolar_jump(waypoint_slicer(build_wp.symbol))
        self.ship_intrasolar(build_wp.symbol)

        cargo = [ci for ci in self.ship.cargo_inventory if ci.symbol == tradegood]
        if len(cargo) > 0:
            self.st.ship_dock(self.ship)
            resp = self.st.construction_supply(
                build_wp, self.ship, tradegood, cargo[0].units
            )
            if not resp:
                self.logger.error("Failed to supply construction site")
                self.st.sleep(SAFETY_PADDING)

    def find_markets_that_export(self, target_tradegood, highest_tradevolume=True):
        # find the market in the system with the highest tradevolume (or lowest)
        return self._find_markets_that_trade(
            target_tradegood, "EXPORT", highest_tradevolume
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
        waypoints = self.st.find_waypoints_by_trait(
            waypoint_slicer(self.agent.headquarters), "MARKETPLACE"
        )
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

    def get_market(self, market_symbol: str) -> "Market":
        if market_symbol not in self.markets:
            wp = self.st.waypoints_view_one(market_symbol)
            self.markets[market_symbol] = self.st.system_market(wp)
        return self.markets[market_symbol]


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "1A"
    ship = f"{agent}-{ship_number}"
    behaviour_params = {
        "priority": 3,
        # "target_wp": "X1-KM71-I60",
        # "market_wps": ["X1-KM71-F52", "X1-KM71-D46"]
        # "market_wp": "X1-YG29-D43",
    }

    bhvr = ConstructJumpgate(agent, ship, behaviour_params or {})

    lock_ship(ship, "MANUAL", 60 * 24)
    bhvr.run()
    lock_ship(ship, "MANUAL", 0)
