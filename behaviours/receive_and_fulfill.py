# currently we don't have a good way of syncing ship state changes between agents.
# therefore, we have to get the current ship each time it boots up.
# survey, and if less than 10 cargo items remaining, sell all except contract deliverables
# if full (less than 10 space remaining), RTB and fulfill.
from behaviours.generic_behaviour import Behaviour
import logging

from straders_sdk.client_api import SpaceTradersApiClient as SpaceTraders
st = SpaceTraders(token)
ships = st.ships_view()
    for ship in ships:     
        print (f"{ship.name} is at {ship.nav.waypoint_symbol}")
    )
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
        ship = self.ship
        st = self.st
        agent = st.view_my_self()
        st.logging_client.log_beginning(BEHAVIOUR_NAME, ship.name, agent.credits)

        if ship.fuel_current < 200:
            st.ship_dock(ship)
            st.ship_refuel(ship)
            st.ship_orbit(ship)
        if "receive_wp" in self.behaviour_params:
            start_waypoint = self.behaviour_params["receive_wp"]
            self.ship_intrasolar(start_waypoint)
        if ship.nav.status != "IN_ORBIT":
            st.ship_orbit(ship)
        if ship.can_survey:
            st.ship_survey(ship)

        if ship.cargo_units_used >= ship.cargo_capacity - 10:
            # lets go get the contract information
            start_waypoint = (
                ship.nav.waypoint_symbol if start_waypoint is None else start_waypoint
            )
            found_contracts = st.view_my_contracts()
            contracts = []
            for id, contract in found_contracts.items():
                if not contract.accepted:
                    resp = st.contract_accept(id)
                    if resp:
                        contracts.append(contract)
                elif contract.accepted and not contract.fulfilled:
                    contracts.append(contract)
            cargo_to_skip = []
            fulfill_waypoint = None
            if len(contracts) > 0:
                for contract in contracts:
                    for item in contract.deliverables:
                        if item.units_fulfilled < item.units_required:
                            fulfill_waypoint = item.destination_symbol
                            cargo_to_skip.append(item.symbol)
            # now we have a list of cargo items to skip
            # lets sell at the current location

            self.sell_all_cargo(cargo_to_skip)

            rtb = False
            for cargo_item in ship.cargo_inventory:
                if cargo_item.symbol in cargo_to_skip:
                    rtb = True

            st.ship_orbit(ship)
            if rtb:
                self.ship_intrasolar(fulfill_waypoint)

                # for deliverables, check if we have them in inventory, and delivery.
                st.ship_dock(ship)
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
                st.ship_orbit(ship)
                self.ship_intrasolar(start_waypoint)

        self.sleep_until_ready()
        st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
        # if we've left over cargo to fulfill, fulfill it.
        # Not sure if it's more efficient to fill up the cargo hold and then fulfill, or to fulfill as we go.
