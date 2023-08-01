import logging
from behaviours.generic_behaviour import Behaviour
from straders_sdk.ship import ShipInventory, Ship
import time

BEHAVIOUR_NAME = "EXTRACT_AND_TRANSFER_OR_SELL"


class ExtractAndTransferAll(Behaviour):
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
        if not ship.can_extract:
            st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
            return

        st.logging_client.log_beginning(BEHAVIOUR_NAME, ship.name, agent.credits)

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
        cargo_to_transfer = self.behaviour_params.get("cargo_to_transfer", [])
        valid_agents = self.behaviour_params.get(
            "valid_agents", [agent.symbol]
        )  # which agents do we transfer quest cargo to?
        self.ship_intrasolar(target_wp_sym)

        # find a hauler - currently restricted to my ships.
        # TODO: create methods for finding ships from other agents
        # TODO: Parameterise which agents we can transfer haulers to

        self.extract_till_full(cargo_to_transfer)

        hauler = self.find_hauler(ship.nav.waypoint_symbol, valid_agents)
        if hauler:
            hauler: Ship
            for cargo in ship.cargo_inventory:
                if cargo.symbol in cargo_to_transfer:
                    resp = st.ship_transfer_cargo(
                        ship, cargo.symbol, cargo.units, hauler.name
                    )
                    if not resp:
                        self.logger.warning(
                            "Failed to transfer cargo to hauler %s %s",
                            hauler.name,
                            resp.error,
                        )
        self.sell_all_cargo(cargo_to_transfer)
        if ship.cargo_units_used == ship.cargo_capacity:
            self.logger.info("Ship unable to do anything, sleeping for 300s")
            time.sleep(300)
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
