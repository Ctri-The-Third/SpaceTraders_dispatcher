# currently we don't have a good way of syncing ship state changes between agents.
# therefore, we have to get the current ship each time it boots up.
# survey, and if less than 10 cargo items remaining, sell all except contract deliverables
# if full (less than 10 space remaining), RTB and fulfill.
import time
import sys


sys.path.append(".")
from behaviours.generic_behaviour import Behaviour
import logging

from straders_sdk.client_api import SpaceTradersApiClient as SpaceTraders
from straders_sdk.ship import Ship
from straders_sdk.utils import waypoint_slicer, set_logging

BEHAVIOUR_NAME = "TAKE_FROM_EXTRACTORS_AND_GO_SELL_9"
SAFETY_PADDING = 60


class TakeFromExactorsAndFulfillOrSell_9(Behaviour):
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
        self.fulfil_wp_s = self.behaviour_params.get("fulfil_wp", None)
        self.start_wp_s = self.behaviour_params.get("asteroid_wp", None)
        self.market_wp_s = self.behaviour_params.get("market_wp", None)
        self.exclusive_cargo_items = self.behaviour_params.get("cargo_to_receive", None)

    def run(self):
        super().run()

        st = self.st
        # we have to use the API call since we don't have inventory in the DB
        ship = self.ship = st.ships_view_one(self.ship.name, True)

        st.ship_cooldown(ship)

        agent = st.view_my_self()
        st.logging_client.log_beginning(BEHAVIOUR_NAME, ship.name, agent.credits)

        #
        # 1. DEFAULT BEHAVIOUR (for if we've not got active orders)
        # 1.1 check what cargo we already have
        # 1.2 check what cargo is in the surrounding extractors
        # 1.3 either fill up our biggest cargo item, or fill up with the most valuable & available cargo item
        #

        #
        # 2. preflight checks (refuel and desintation checking)
        #

        start_sys = st.systems_view_one(waypoint_slicer(self.start_wp_s))
        start_wp = st.waypoints_view_one(start_sys.symbol, self.start_wp_s)
        destination_sys = st.systems_view_one(
            waypoint_slicer(self.market_wp_s or self.fulfil_wp_s)
        )

        self.ship_extrasolar(start_sys)
        self.ship_intrasolar(start_wp.symbol)

        #
        # 3. ACQUIRE DESIRED CARGO FROM NEIGHBOURING EXTRACTORS
        #
        cargo_remaining = ship.cargo_space_remaining
        neighbours = self.get_neighbouring_extractors()
        for target in self.exclusive_cargo_items:
            if cargo_remaining == 0:
                break
            for neighbour in neighbours:
                if cargo_remaining == 0:
                    break
                neighbour: Ship
                for cargo_item in neighbour.cargo_inventory:
                    if cargo_item.symbol == target:
                        transfer_amount = min(cargo_item.units, cargo_remaining)
                        resp = st.ship_transfer_cargo(
                            neighbour, cargo_item.symbol, transfer_amount, ship.name
                        )
                        if resp:
                            cargo_remaining -= transfer_amount
                            if cargo_remaining == 0:
                                break
                        # we have a match
        self.ship = ship = st.ships_view_one(self.ship.name, True)
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
            self.ship_intrasolar(self.fulfil_wp_s or self.market_wp_s)

            st.ship_dock(ship)

            managed_to_fulfill = False
            if self.fulfil_wp_s:
                resp = self.fulfil_any_relevant()
                if resp:  # we fulfilled something
                    managed_to_fulfill = True
                    # we fulfilled something, so we should be able to sell the rest
                    st.ship_orbit(ship)
                    self.ship_extrasolar(start_sys)
                    self.ship_intrasolar(self.start_wp_s)
            elif self.market_wp_s:
                # we got to the fulfill point but something went horribly wrong
                market = st.system_market(
                    st.waypoints_view_one(destination_sys, self.market_wp_s)
                )
                resp = self.sell_all_cargo(market=market)

                st.system_market(
                    st.waypoints_view_one(destination_sys, self.market_wp_s), True
                )
                if resp:
                    st.ship_orbit(ship)
                    self.ship_extrasolar(start_sys)
                    self.ship_intrasolar(self.start_wp_s)

                    # we added this in for circumstances when we've incorrect, left over cargo in the hold that needs drained. Might need a "vent all" option too.
                    # self.sell_all_cargo()

            if ship.cargo_units_used >= ship.cargo_capacity - 10:
                # something's gone horribly wrong, we couldn't sell or fulfill at the destination - are our orders stale?
                self.ship_extrasolar(start_sys)
                self.ship_intrasolar(self.start_wp_s)

        else:
            if ship.nav.waypoint_symbol != self.start_wp_s:
                self.ship_extrasolar(start_sys)
                self.ship_intrasolar(self.start_wp_s)
            else:
                time.sleep(SAFETY_PADDING)
            # sleep for 60 seconds

        self.sleep_until_ready()
        self.end()
        st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
        # if we've left over cargo to fulfill, fulfill it.
        # Not sure if it's more efficient to fill up the cargo hold and then fulfill, or to fulfill as we go.

    def get_neighbouring_extractors(self):
        ships = self.st.ships_view()
        ships = [
            s
            for s in ships.values()
            if s.nav.waypoint_symbol == self.ship.nav.waypoint_symbol
        ]
        ships = [s for s in ships if s.role == "EXCAVATOR"]
        return ships


if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "5"
    ship = f"{agent}-{ship_number}"
    behaviour_params = {
        "priority": 4,
        "market_wp": "X1-U49-H53",
        "asteroid_wp": "X1-U49-FA4A",
        "cargo_to_receive": ["ALUMINUM_ORE", "COPPER_ORE", "IRON_ORE"],
    }
    bhvr = TakeFromExactorsAndFulfillOrSell_9(agent, ship, behaviour_params or {})
    lock_ship(ship_number, "MANUAL", bhvr.st.db_client.connection, 60 * 24)
    bhvr.run()
    lock_ship(ship_number, "MANUAL", bhvr.st.db_client.connection, 0)