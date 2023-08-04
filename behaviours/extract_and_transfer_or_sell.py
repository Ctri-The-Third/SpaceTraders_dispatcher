import sys

sys.path.append(".")
import logging
from behaviours.generic_behaviour import Behaviour
from straders_sdk.ship import ShipInventory, Ship
import time

BEHAVIOUR_NAME = "EXTRACT_AND_TRANSFER_OR_SELL"


class ExtractAndTransferOrSell_4(Behaviour):
    def __init__(
        self,
        agent_name,
        ship_name,
        behaviour_params: dict = {},
        config_file_name="user.json",
    ) -> None:
        super().__init__(agent_name, ship_name, behaviour_params, config_file_name)
        self.logger = logging.getLogger("bhvr_extract_and_transfer")
        self.logger.info("initialising...")

    def run(self):
        ship = self.ship
        st = self.st
        agent = st.view_my_self()

        #
        #  -- log beginning
        #
        if not ship.can_extract:
            st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
            return

        st.logging_client.log_beginning(BEHAVIOUR_NAME, ship.name, agent.credits)

        #
        # -- navigate to target waypoint - if not set, go for nearest asteroid field
        #
        try:
            target_wp_sym = self.behaviour_params.get(
                "extract_waypoint",
                st.find_waypoint_by_type(
                    ship.nav.system_symbol, "ASTEROID_FIELD"
                ).symbol,
            )
        except AttributeError as e:
            self.logger.error("could not find waypoints because %s", e)
            self.logger.info("Triggering waypoint cache refresh. Rerun behaviour.")
            st.waypoints_view(ship.nav.system_symbol, True)
            return

        self.ship_intrasolar(target_wp_sym)
        #
        #  - identify precious cargo materials - we will use surveys for these and transfer to hauler.
        #

        cargo_to_transfer = self.behaviour_params.get("cargo_to_transfer", [])
        if cargo_to_transfer == []:
            contracts = st.view_my_contracts()
            for contract_id, contract in contracts.items():
                if (not contract.accepted) or contract.fulfilled:
                    continue
                for deliverable in contract.deliverables:
                    if deliverable.units_fulfilled < deliverable.units_required:
                        cargo_to_transfer.append(deliverable.symbol)

        self.extract_till_full(cargo_to_transfer)

        #
        # find a hauler from any of the matching agents.
        #

        valid_agents = self.behaviour_params.get(
            "valid_agents", [agent.symbol]
        )  # which agents do we transfer quest cargo to?

        hauler = self.find_hauler(ship.nav.waypoint_symbol, valid_agents)
        if hauler:
            hauler: Ship
            hauler_space = hauler.cargo_capacity - hauler.cargo_units_used

            for cargo in ship.cargo_inventory:
                if cargo.symbol in cargo_to_transfer:
                    resp = st.ship_transfer_cargo(
                        ship, cargo.symbol, min(cargo.units, hauler_space), hauler.name
                    )
                    if not resp:
                        st.ships_view_one(hauler.name, True)
                        self.logger.warning(
                            "Failed to transfer cargo to hauler %s %s",
                            hauler.name,
                            resp.error,
                        )

        #
        # sell all remaining cargo now we're full.
        #
        self.sell_all_cargo(cargo_to_transfer)
        if ship.cargo_units_used == ship.cargo_capacity:
            self.logger.info("Ship unable to do anything, sleeping for 300s")
            time.sleep(300)

        #
        # end of script.
        #
        st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)

    def find_hauler(self, waypoint_symbol, valid_agents: list):
        st = self.st

        my_ships = st.ships_view()

        haulers = [
            ship for id, ship in my_ships.items() if ship.role in ["HAULER", "COMMAND"]
        ]
        for hauler in haulers:
            hauler: Ship
            if hauler.nav.waypoint_symbol == waypoint_symbol:
                remaining_space = hauler.cargo_capacity - hauler.cargo_units_used
                if remaining_space == 0:
                    continue
                return hauler
        return None


if __name__ == "__main__":
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI"
    ship = sys.argv[2] if len(sys.argv) > 2 else "CTRI-6"
    bhvr = ExtractAndTransferOrSell_4(agent, ship)
    bhvr.run()
