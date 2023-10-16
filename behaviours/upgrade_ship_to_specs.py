# This behaviour will go extrasoloar to the best place for a given item
#  then take it to the assigned location/ship and then transfer/sell the cargo


import sys

sys.path.append(".")
from straders_sdk.utils import waypoint_slicer, try_execute_select, set_logging
from behaviours.generic_behaviour import Behaviour
from straders_sdk.models import System
import logging
import time
import math

from straders_sdk.client_api import SpaceTradersApiClient as SpaceTraders

BEHAVIOUR_NAME = "UPGRADE_TO_SPEC"
SAFETY_PADDING = 60


class FindMountsAndEquip(Behaviour):
    """Requires a parameter blob containing

    `mounts`: a list of the mount symbols to equip\n
    `market_wp`: the waypoint symbol of the market to buy all the mounts from\n"""

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
        ship = self.ship
        st = self.st
        agent = st.view_my_self()
        st.logging_client.log_beginning(BEHAVIOUR_NAME, ship.name, agent.credits)

        mounts = self.behaviour_params["mounts"]
        ship_mounts = [mount.symbol for mount in ship.mounts]
        starting_system = st.systems_view_one(ship.nav.system_symbol)
        sell_unequipped_mounts = True

        missing_mounts = []
        for target_mount in mounts:
            got_it = False
            index = 0
            for my_mount in ship_mounts:
                if my_mount == target_mount:
                    got_it = True
                    break
                index += 1
            # stops one equipped mount from meeting multiple requirements

            if got_it:
                ship_mounts.pop(index)
                continue
            else:
                missing_mounts.append(target_mount)

        # at this point, ship_mounts contains all the excess mounts we need to get rid of. Find the nearest shipyard and execute.
        if len(ship_mounts) > 0:
            self.goto_shipyard(starting_system)
            st.ship_dock(ship)
            for mount in ship_mounts:
                resp = st.ship_remove_mount(ship, mount)
                if not resp:
                    self.logger.error(
                        "Couldn't remove mount %s because %s", mount, resp.error
                    )
                    time.sleep(SAFETY_PADDING)
                    continue

            #
            # we now have all the space necessary for the mounts.
            #

        # equip any stored mounts
        for target_mount in missing_mounts:
            for inventory in ship.cargo_inventory:
                if inventory.symbol == target_mount:
                    self.goto_shipyard(starting_system)
                    st.ship_dock(ship)
                    resp = st.ship_install_mount(ship, target_mount)
                    missing_mounts.pop(missing_mounts.index(target_mount))

        # buy any still missing mounts
        for target_mount in missing_mounts:
            #
            #

            #
            # choose the best waypoint (does not factor in lost CPS/ best cost per distance)
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
                for mount in ship_mounts:  # sell the unwanted stuff
                    resp = st.ship_sell(ship, mount, 1)

        # now we have all the missing mounts, equip em
        for target_mount in missing_mounts:
            self.goto_shipyard(destination_sys)
            st.ship_dock(ship)
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
        current_system = st.systems_view_one(ship.nav.system_symbol)
        for item in ship.cargo_inventory:
            destinations = self.find_best_market_systems_to_sell(item.symbol)
            best_destination = None
            best_distance = 9999999999
            best_cpj = 0

            # work out the best credits per jump. If we're in the same system, assume it's all the same even if there's multiple markets.
            for destination in destinations:
                dest_sys = destination[1]
                dest_sys: System
                price = destination[2]
                distance = math.sqrt(
                    (dest_sys.x - current_system.x) ** 2
                    + (dest_sys.y - current_system.y) ** 2
                )
                # if we're in the same system,
                if dest_sys.symbol == current_system.symbol:
                    cpj = price / 1
                    jumps = 0
                # 2000 is one jump gate away, so any thing that's conceivably AT LEAST 2 jumps away gets checked
                elif distance < (best_distance + 2000) * 2:
                    route = self.pathfinder.astar(current_system, dest_sys)
                    jumps = route.route if route is not None else []
                    cpj = price / (jumps + 1)
                else:
                    cpj = 0
                    jumps = 0

                if cpj > best_cpj:
                    best_cpj = cpj
                    best_jumps = jumps
                    best_distance = distance
                    best_destination_sys = dest_sys
                    best_destination_wp = destination[0]
            self.ship_extrasolar(best_destination_sys)
            self.ship_intrasolar(best_destination_wp)
            st.ship_dock(ship)
            st.ship_sell(ship, item.symbol, item.units)
        self.end()
        self.st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)

    def goto_shipyard(self, starting_system):
        st = self.st
        target_system = self.find_nearest_systems_by_waypoint_trait(
            starting_system, "SHIPYARD", 50000, True
        )

        if not target_system.symbol:
            self.logger.error("Couldn't find a shipyard to sell excess mounts to!")
            time.sleep(SAFETY_PADDING)
        else:
            target_system = st.systems_view_one(target_system.symbol)
            target_wp = st.find_waypoints_by_trait_one(target_system.symbol, "SHIPYARD")
            self.ship_extrasolar(target_system)
            self.ship_intrasolar(target_wp)

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
            distance = self.pathfinder.astar(start_system, dest_system)
            if distance.jumps >= 0:
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
    from dispatcherWK12 import lock_ship

    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    # 3, 4,5,6,7,8,9
    # A is the surveyor
    ship_suffix = sys.argv[2] if len(sys.argv) > 2 else "1"
    ship = f"{agent}-{ship_suffix}"

    bhvr = FindMountsAndEquip(
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
    lock_ship(ship, "MANUAL", bhvr.connection, duration=120)
    set_logging(logging.DEBUG)
    bhvr.run()
    lock_ship(ship, "", bhvr.connection, duration=0)
