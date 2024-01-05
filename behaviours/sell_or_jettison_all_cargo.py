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

BEHAVIOUR_NAME = "SELL_OR_JETTISON_ALL_CARGO"
SAFETY_PADDING = 180


class SellOrDitch(Behaviour):
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
        ship = self.ship = st.ships_view_one(self.ship_name, True)
        ship: Ship
        agent = st.view_my_self()
        current_location = st.waypoints_view_one(ship.nav.waypoint_symbol)
        waypoints = st.find_waypoints_by_trait(ship.nav.system_symbol, "MARKETPLACE")
        waypoints_d = {w.symbol: w for w in waypoints}
        if waypoints:
            markets = [
                st.system_market(m)
                for m in waypoints
                if m.symbol != ship.nav.waypoint_symbol
            ]
        else:
            markets = []
        for cargo in ship.cargo_inventory:
            best_market = None
            best_value = 0
            for m in markets:
                tg = m.get_tradegood(cargo.symbol)
                if not tg:
                    continue
                wp = waypoints_d[m.symbol]
                distance = (
                    self.pathfinder.calc_distance_between(current_location, wp) + 15
                )

                if tg.sell_price / distance > best_value:
                    best_market = m
                    best_value = tg.sell_price / distance
            if best_market:
                tg = best_market.get_tradegood(cargo.symbol)
                self.ship_intrasolar(best_market.symbol)
                st.ship_dock(ship)
                resp = st.ship_sell(
                    ship, cargo.symbol, min(cargo.units, tg.trade_volume)
                )
                if not resp:
                    self.logger.error(
                        f"Failed to sell {cargo.symbol} because {resp.error}"
                    )
                    continue
            else:
                st.ship_jettison_cargo(ship, cargo.symbol, cargo.units)


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "1"
    ship = f"{agent}-{ship_number}"
    behaviour_params = {
        "priority": 3,
    }

    bhvr = SellOrDitch(agent, ship, behaviour_params or {})

    lock_ship(ship_number, "MANUAL", bhvr.st.db_client.connection, 60 * 24)
    bhvr.run()
    lock_ship(ship_number, "MANUAL", bhvr.st.db_client.connection, 0)
