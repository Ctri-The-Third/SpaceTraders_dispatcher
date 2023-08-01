import logging
from behaviours.generic_behaviour import Behaviour
from straders_sdk.ship import ShipInventory, Ship
import time

BEHAVIOUR_NAME = "EXTRACT_AND_TRANSFER_HIGHEST"


class ExtractAndTransferHeighest_1(Behaviour):
    def __init__(
        self,
        agent_name,
        ship_name,
        behaviour_params: dict = {},
        config_file_name="user.json",
    ) -> None:
        super().__init__(agent_name, ship_name, behaviour_params, config_file_name)
        self.logger = logging.getLogger("bhvr_extract_and_transfer")
        self.st.logging_client.log_beginning(
            BEHAVIOUR_NAME, ship_name, self.st.view_my_self().credits
        )

    def run(self):
        ship = self.ship
        st = self.st
        agent = st.view_my_self()
        if not ship.can_extract:
            st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
            return

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
        self.extract_till_full()

        if len(ship.cargo_inventory) == 0:
            st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
            return
        largest_allocation = ShipInventory("", "", "", 0)
        for item in ship.cargo_inventory:
            if item.units > largest_allocation.units:
                largest_allocation = item

        # find a hauler - currently restricted to my ships.
        # TODO: create methods for finding ships from other agents
        # TODO: Parameterise which agents we can transfer haulers to

        success = False
        my_ships = st.ships_view()
        haulers = [
            ship for id, ship in my_ships.items() if ship.role in ["HAULER", "COMMAND"]
        ]
        for hauler in haulers:
            hauler: Ship
            if hauler.nav.waypoint_symbol == target_wp_sym:
                remaining_space = hauler.cargo_capacity - hauler.cargo_units_used
                to_transfer = min(remaining_space, largest_allocation.units)
                if to_transfer == 0:
                    continue
                resp = st.ship_transfer_cargo(
                    ship,
                    largest_allocation.symbol,
                    to_transfer,
                    hauler.name,
                )
                if resp:
                    success = True
                    break
        if not success:
            self.logger.warning(
                "No haulers available to transfer to - ship full, sleeping for 70s"
            )
            time.sleep(70)
        st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
