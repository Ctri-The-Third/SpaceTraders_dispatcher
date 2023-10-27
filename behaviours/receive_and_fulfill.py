# currently we don't have a good way of syncing ship state changes between agents.
# therefore, we have to get the current ship each time it boots up.
# survey, and if less than 10 cargo items remaining, sell all except contract deliverables
# if full (less than 10 space remaining), RTB and fulfill.

import sys

sys.path.append(".")
from behaviours.generic_behaviour import Behaviour
import logging

from straders_sdk.client_api import SpaceTradersApiClient as SpaceTraders
from straders_sdk.utils import waypoint_slicer, set_logging

BEHAVIOUR_NAME = "RECEIVE_AND_FULFILL"


class ReceiveAndFulfillOrSell_3(Behaviour):
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

    def run(self):
        super().run()
        st = self.st
        ship = self.ship
        st.ship_cooldown(ship)

        agent = st.view_my_self()
        st.logging_client.log_beginning(BEHAVIOUR_NAME, ship.name, agent.credits)

        fulfil_wp_s = self.behaviour_params.get("fulfil_wp", None)
        start_wp_s = self.behaviour_params.get("asteroid_wp", ship.nav.waypoint_symbol)
        start_sys = st.systems_view_one(waypoint_slicer(start_wp_s))
        market_wp_s = self.behaviour_params.get("market_wp", None)
        exclusive_cargo_items = self.behaviour_params.get("cargo_to_receive", None)

        #
        # 1. DEFAULT BEHAVIOUR (for if we've not got active orders)
        #

        if not market_wp_s and not fulfil_wp_s and ship.cargo_units_used > 0:
            # sell to the best market, based on CPR
            # assume 8 base CPR, with 1 CPR per jump
            # find all relevant market systems, get their distances and value
            # for the ones with the greatest value/distance(1), get the top 5
            item_with_highest_quantity = max(
                ship.cargo_inventory, key=lambda item: item.units
            )

            markets = self.find_best_market_systems_to_sell(
                item_with_highest_quantity.symbol
            )
            # markets is a tuple, where the items are waypoint_s, system, price
            paths = {
                system[0]: self.pathfinder.astar(start_sys, system[1])
                for system in markets
            }
            best_cpr = 0
            best_cpr_system = None
            for wp_s, _, price in markets:
                path = paths.get(wp_s, None)
                if not path:
                    continue
                request_count = (
                    path.jumps + 6
                )  # this is my guesstimate for receive offset,  navigatting, [jumps] navigating, docking, selling, undocking
                print(
                    f"request count for {wp_s} is {request_count}, price is {price}, cpr is {price / request_count}"
                )
                cpr = price / request_count
                if cpr > best_cpr:
                    best_cpr = cpr
                    best_cpr_system = wp_s
            market_wp_s = best_cpr_system  # find_market_in_system?

        #
        # 2. preflight checks (refuel and desintation checking)
        #

        destination_sys = st.systems_view_one(
            waypoint_slicer(market_wp_s or fulfil_wp_s or start_wp_s)
        )

        if ship.fuel_current < min(ship.fuel_capacity, 200):
            st.ship_dock(ship)
            st.ship_refuel(ship)
            st.ship_orbit(ship)
        if ship.nav.status != "IN_ORBIT":
            st.ship_orbit(ship)
        if ship.can_survey:
            st.ship_survey(ship)
        # Check we're full, prep and deploy

        #
        # 3. JETTISON UNWANTED CARGO
        #

        if exclusive_cargo_items:
            for cargo_item in ship.cargo_inventory:
                if cargo_item.symbol not in exclusive_cargo_items:
                    st.ship_jettison_cargo(ship, cargo_item.symbol, cargo_item.units)

        #
        # 4. NAVIGATE AND DELIVER/ SELL CARGO
        #

        if ship.cargo_units_used >= ship.cargo_capacity - 10:
            # are we doing a sell, or a contract?
            # check if we have a contract for the items in our inventory
            found_contracts = st.view_my_contracts()
            contracts = []
            for contract in found_contracts:
                if contract.accepted and not contract.fulfilled:
                    contracts.append(contract)
            cargo_to_skip = []
            # if len(contracts) > 0:
            #    for contract in contracts:
            #        for item in contract.deliverables:
            #            if item.units_fulfilled < item.units_required:
            #                fulfill_wp_s = item.destination_symbol
            #                cargo_to_skip.append(item.symbol)

            st.ship_orbit(ship)
            self.ship_extrasolar(destination_sys)
            self.ship_intrasolar(fulfil_wp_s or market_wp_s)

            st.ship_dock(ship)

            managed_to_fulfill = False
            if fulfil_wp_s:
                resp = self.fulfil_any_relevant()
                if resp:  # we fulfilled something
                    managed_to_fulfill = True
                    # we fulfilled something, so we should be able to sell the rest
                    st.ship_orbit(ship)
                    self.ship_extrasolar(start_sys)
                    self.ship_intrasolar(start_wp_s)
            elif market_wp_s:
                # we got to the fulfill point but something went horribly wrong
                market = st.system_market(
                    st.waypoints_view_one(destination_sys, market_wp_s)
                )
                resp = self.sell_all_cargo(market=market)

                st.system_market(
                    st.waypoints_view_one(destination_sys, market_wp_s), True
                )
                if resp:
                    st.ship_orbit(ship)
                    self.ship_extrasolar(start_sys)
                    self.ship_intrasolar(start_wp_s)

                    # we added this in for circumstances when we've incorrect, left over cargo in the hold that needs drained. Might need a "vent all" option too.
                    # self.sell_all_cargo()

            if ship.cargo_units_used >= ship.cargo_capacity - 10:
                # something's gone horribly wrong, we couldn't sell or fulfill at the destination - are our orders stale?
                self.ship_extrasolar(start_sys)
                self.ship_intrasolar(start_wp_s)

        else:
            self.ship_extrasolar(start_sys)
            self.ship_intrasolar(start_wp_s)

        self.sleep_until_ready()
        self.end()
        st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
        # if we've left over cargo to fulfill, fulfill it.
        # Not sure if it's more efficient to fill up the cargo hold and then fulfill, or to fulfill as we go.


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "3A"
    ship = f"{agent}-{ship_number}"
    behaviour_params = {"asteroid_wp": "X1-RV57-69965Z"}
    bhvr = ReceiveAndFulfillOrSell_3(agent, ship, behaviour_params or {})
    lock_ship(ship_number, "MANUAL", bhvr.st.db_client.connection, 60 * 24)
    bhvr.run()
    lock_ship(ship_number, "MANUAL", bhvr.st.db_client.connection, 0)
