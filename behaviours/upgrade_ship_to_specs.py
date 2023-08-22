# This behaviour will go extrasoloar to the best place for a given item
#  then take it to the assigned location/ship and then transfer/sell the cargo


import sys

sys.path.append(".")
from straders_sdk.utils import waypoint_slicer, try_execute_select, set_logging
from behaviours.generic_behaviour import Behaviour
import logging
import time
import math

from straders_sdk.client_api import SpaceTradersApiClient as SpaceTraders

BEHAVIOUR_NAME = "UPGRADE_TO_SPEC"
SAFETY_PADDING = 60


class FindModulesAndEquip(Behaviour):
    """Requires a parameter blob containing

    `mounts`: a list of the mount symbols to equip\n"""

    def __init__(
        self,
        agent_name,
        ship_name,
        behaviour_params: dict = ...,
        config_file_name="user.json",
    ) -> None:
        super().__init__(agent_name, ship_name, behaviour_params, config_file_name)
        self.logger = logging.getLogger(BEHAVIOUR_NAME)

    def run(self):
        super().run()
        ship = self.ship
        st = self.st
        agent = st.view_my_self()
        st.logging_client.log_beginning(BEHAVIOUR_NAME, ship.name, agent.credits)

        mounts = self.behaviour_params["mounts"]
        ship_mounts = [mount.symbol for mount in ship.mounts]
        for target_mount in mounts:
            index = 0
            got_it = False
            for my_mount in ship_mounts:
                if my_mount == target_mount:
                    got_it = True
                    break
                index += 1
            # stops one equipped mount from meeting multiple requirements

            if got_it:
                ship_mounts.pop(index)

                continue
            #
            # is it already in our inventory? if so, skip this step, and just try and equip it.
            #
            for inventory in ship.cargo_inventory:
                if inventory.symbol == target_mount:
                    st.ship_install_mount(ship, target_mount)
                    continue
            #
            # choose the best waypoint, factoring in lost CPS
            #
            destination_wp_sym = self.find_cheapest_markets_for_good(target_mount)
            if not destination_wp_sym:
                self.logger.error("Couldn't find mount %s", target_mount)
                time.sleep(SAFETY_PADDING)
                continue
            system_sym = waypoint_slicer(destination_wp_sym)
            destination_sys = st.systems_view_one(system_sym)
            if ship.nav.system_symbol != system_sym:
                resp = self.ship_extrasolar(destination_sys)
                if not resp:
                    time.sleep(SAFETY_PADDING)
                    continue
            if ship.nav.waypoint_symbol != destination_wp_sym:
                resp = self.ship_intrasolar(destination_wp_sym)
                if not resp:
                    time.sleep(SAFETY_PADDING)
                    continue

            if ship.nav.waypoint_symbol == destination_wp_sym:
                st.ship_dock(ship)
                resp = st.ship_purchase_cargo(ship, target_mount, 1)

                if not resp:
                    time.sleep(SAFETY_PADDING)
                    continue

                resp = st.ship_install_mount(ship, target_mount)
                if not resp:
                    time.sleep(SAFETY_PADDING)
                    continue

        # check what mounts we still need (including what's in cargo)
        # go to a shipyard with mounts we're missing
        # acquire mounts
        # equip mounts

        #
        # setup initial parameters and preflight checks
        #

    def find_cheapest_markets_for_good(
        self, tradegood_sym: str, opportunity_cost_cps: int = 200
    ) -> list[str]:
        st = self.st
        ship = self.ship
        sql = """select market_symbol, purchase_price from market_tradegood_listings
where trade_symbol = %s
order by purchase_price asc """
        wayps = try_execute_select(self.connection, sql, (tradegood_sym,))

        if not wayps:
            self.logger.error(
                "Couldn't find cheapest market for good %s", tradegood_sym
            )
            return None

        destination_wps_and_prices = wayps
        start_system = st.systems_view_one(ship.nav.system_symbol)
        markets = []
        for market in destination_wps_and_prices:
            dest_system = st.systems_view_one(waypoint_slicer(market[0]))
            distance = self.astar(self.graph, start_system, dest_system)
            if not distance:
                continue
            obj = (market[0], market[1], len(distance))
            markets.append(obj)
            # if we a assume a jump is worth 4 minutes of intrasolar and 6 minutes of cooldown and a CPM of like 200, then the cost of a jump is ~2400 credits per jump + 1600 for being more than 0.

        best_cost = sys.maxsize
        destination_wp_sym = None
        for market in markets:
            # price = market[1]
            # opportunity cost = 2400 * (len(distance) - 1) + 1600 if len(distance) > 1 else 0
            cost = market[1] + (2400 * (market[2] - 1) + 1600 if market[2] > 0 else 0)
            if cost < best_cost:
                best_cost = cost
                destination_wp_sym = market[0]

        return destination_wp_sym


if __name__ == "__main__":
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-L8-"
    ship_suffix = sys.argv[2] if len(sys.argv) > 2 else "1"
    ship = f"{agent}-{ship_suffix}"
    bhvr = FindModulesAndEquip(
        agent,
        ship,
        behaviour_params={
            "mounts": [
                "MOUNT_MINING_LASER_II",
                "MOUNT_MINING_LASER_II",
                "MOUNT_MINING_LASER_I",
            ]
        },
    )
    set_logging(logging.DEBUG)
    bhvr.run()
