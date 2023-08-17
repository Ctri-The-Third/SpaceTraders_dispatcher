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
    ) -> None:
        super().__init__(agent_name, ship_name, behaviour_params, config_file_name)
        self.logger = logging.getLogger("bhvr_receive_and_fulfill")

    def run(self):
        super().run()
        st = self.st
        ship = self.ship
        st.ship_cooldown(ship)

        agent = st.view_my_self()
        st.logging_client.log_beginning(BEHAVIOUR_NAME, ship.name, agent.credits)

        fulfill_wp_s = None
        start_wp_s = self.behaviour_params.get("asteroid_wp", ship.nav.waypoint_symbol)
        start_sys = st.systems_view_one(waypoint_slicer(start_wp_s))
        market_wp_s = self.behaviour_params.get("market_wp", None)

        destination_sys = st.systems_view_one(
            waypoint_slicer(market_wp_s or fulfill_wp_s)
        )

        if ship.fuel_current < min(ship.fuel_capacity, 200):
            st.ship_dock(ship)
            st.ship_refuel(ship)
            st.ship_orbit(ship)
        if ship.nav.status != "IN_ORBIT":
            st.ship_orbit(ship)
        if ship.can_survey:
            st.ship_survey(ship)
        # we're full, prep and deploy
        if (
            ship.cargo_units_used >= ship.cargo_capacity - 10
            or ship.nav.system_symbol == destination_sys.symbol
        ):
            # are we doing a sell, or a contract?
            # check if we have a contract for the items in our inventory
            found_contracts = st.view_my_contracts()
            contracts = []
            for id, contract in found_contracts.items():
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
            self.ship_intrasolar(market_wp_s or fulfill_wp_s)

            st.ship_dock(ship)
            if fulfill_wp_s:
                for contract in contracts:
                    for item in contract.deliverables:
                        if item.units_fulfilled < item.units_required:
                            for cargo_item in ship.cargo_inventory:
                                if item.symbol == cargo_item.symbol:
                                    st.contracts_deliver(
                                        contract,
                                        ship,
                                        cargo_item.symbol,
                                        cargo_item.units,
                                    )
            else:
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

        self.sleep_until_ready()
        st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
        # if we've left over cargo to fulfill, fulfill it.
        # Not sure if it's more efficient to fill up the cargo hold and then fulfill, or to fulfill as we go.


if __name__ == "__main__":
    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-UWK5-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "12"
    ship = f"{agent}-{ship_number}"
    bhvr = ReceiveAndFulfillOrSell_3(
        agent,
        ship,
        behaviour_params={
            "market_wp": "X1-JJ96-77642Z",
            "asteroid_wp": "X1-YA22-87615D",
        },
    )
    bhvr.run()
