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

BEHAVIOUR_NAME = "REFUEL_STRANDED"
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
        self.target_ships = self.behaviour_params.get("target_ships", [])

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
        agent = st.view_my_self()

        if not self.target_ships:
            self.logger.info("No target ships specified, exiting")
            return

        # get a list of distinct waypoints
        all_ships = st.ships_view()
        target_ships = [ship for s, ship in all_ships.items() if s in self.target_ships]
        waypoints_with_stranded_ships = set(
            [ship.nav.waypoint_symbol for ship in target_ships]
        )
        total_fuel_required = math.ceil(
            sum([math.ceil(ship.fuel_capacity / 100) for ship in target_ships])
        )
        fuel_in_inventory = sum(
            [c.units for c in ship.cargo_inventory if c.symbol == "FUEL"]
        )
        total_fuel_required -= fuel_in_inventory
        # can we buy fuel locally?
        # if so - buy and continue
        all_markets = st.find_waypoints_by_trait(ship.nav.system_symbol, "MARKETPLACE")
        start_wp = st.waypoints_view_one(ship.nav.waypoint_symbol)
        fuel_market = None
        closest_distance = float("inf")
        for waypoint in waypoints_with_stranded_ships:
            start_wp = st.waypoints_view_one(waypoint)
            for market_wp in all_markets:
                market_wp: Waypoint
                if market_wp.symbol == waypoint:
                    fuel_market = market_wp.symbol  # shuoldn't happen
                    break
                distance = self.pathfinder.calc_distance_between(market_wp, start_wp)
                if distance < closest_distance:
                    closest_distance = distance
                    fuel_market = market_wp.symbol

            pass
            if total_fuel_required > 0:
                self.ship_intrasolar(fuel_market)
                self.buy_cargo("FUEL", total_fuel_required)

            self.ship_intrasolar(start_wp.symbol)
            for target_ship in target_ships:
                ship_fuel_needed = math.ceil(
                    (target_ship.fuel_capacity - target_ship.fuel_current) / 100
                )
                if target_ship.cargo_space_remaining < ship_fuel_needed:
                    # we need to jettison cargo
                    self.ship_intrasolar(target_ship.nav.waypoint_symbol)

                    space_needed = ship_fuel_needed
                    while space_needed > 0:
                        st.ship_jettison_cargo(
                            target_ship,
                            target_ship.cargo_inventory[0].symbol,
                            min(space_needed, target_ship.cargo_inventory[0].units),
                        )
                        space_needed = ship_fuel_needed - ship.cargo_space_remaining
                if target_ship.nav.status == "DOCKED":
                    st.ship_dock(ship)
                st.ship_transfer_cargo(
                    ship,
                    "FUEL",
                    math.ceil(target_ship.fuel_capacity / 100),
                    target_ship.name,
                )
                st.ship_dock(target_ship)
                st.ship_refuel(target_ship, True)

        # for each waypoint:
        # find the nearest market to that waypoint
        # if amount of remaining fuel less than what we've got in inventory - go here and buy fuel

        # go to the waypoint

        # for each ship at the waypoint:
        # remote jettison cargo, transfer fuel, remote dock and remote refuel from inventory any ships that are there


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "1"
    ship = f"{agent}-{ship_number}"
    behaviour_params = {
        "priority": 3,
        "target_ships": [
            "CTRI-U--15",
            "CTRI-U--13",
            "CTRI-U--A",
            "CTRI-U--10",
            "CTRI-U--8",
            "CTRI-U--12",
            "CTRI-U--F",
        ],
    }

    bhvr = ConstructJumpgate(agent, ship, behaviour_params or {})

    lock_ship(ship_number, "MANUAL", bhvr.st.db_client.connection, 60 * 24)
    bhvr.run()
    lock_ship(ship_number, "MANUAL", bhvr.st.db_client.connection, 0)
