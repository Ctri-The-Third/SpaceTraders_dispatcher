import logging
from .generic_behaviour import Behaviour
from straders_sdk.ship import ShipInventory, Ship
import time

BEHAVIOUR_NAME = "EXTRACT_AND_TRANSFER_ALL"


class ExtractAndTransferAll_2(Behaviour):
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
        super().run()
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
                st.find_waypoints_by_type_one(
                    ship.nav.system_symbol, "ASTEROID_FIELD"
                ).symbol,
            )
        except AttributeError as e:
            self.logger.error("could not find waypoints because %s", e)
            self.logger.info("Triggering waypoint cache refresh. Rerun behaviour.")
            st.waypoints_view(ship.nav.system_symbol, True)
            return

        self.ship_intrasolar(target_wp_sym)

        # find a hauler - currently restricted to my ships.
        # TODO: create methods for finding ships from other agents
        # TODO: Parameterise which agents we can transfer haulers to

        success = False
        self.extract_and_transfer_10_times()
        if not success:
            self.logger.warning(
                "No haulers available to transfer to - ship full, sleeping for 70s"
            )
            time.sleep(70)
        st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)

    def extract_and_transfer_10_times(self):
        ship = self.ship
        st = self.st
        if ship.nav.status != "IN_ORBIT":
            st.ship_orbit(ship)

        for i in range(10):
            extract_success = False
            transfer_success = False
            extract_resp = st.ship_extract(ship)
            extract_success = bool(extract_resp)
            if not extract_success:
                # couldn't extract (cooldown?)
                self.sleep_until_ready()
            hauler = self.find_hauler(ship.nav.waypoint_symbol)
            if hauler:
                space_remaining = hauler.cargo_capacity - hauler.cargo_units_used
                for cargo in ship.cargo_inventory:
                    to_transfer = min(cargo.units, space_remaining)
                    if to_transfer > 0:
                        resp = st.ship_transfer_cargo(
                            ship,
                            cargo.symbol,
                            to_transfer,
                            hauler.name,
                        )
                        if resp:
                            space_remaining -= to_transfer
                            transfer_success = True
            else:
                self.sleep_until_ready()

            if not extract_success and not transfer_success:
                self.logger.warning(
                    "No haulers available to transfer to - ship couldn't extract, sleeping for 70s"
                )
                time.sleep(70)
                return
            # transfer
            # if ship.cargo_capacity == ship.cargo_units_used:
            #     break

    def find_hauler(self, waypoint_symbol):
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
