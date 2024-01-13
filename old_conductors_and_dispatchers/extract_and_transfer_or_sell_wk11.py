import sys

sys.path.append(".")
import logging
from behaviours.generic_behaviour import Behaviour
from straders_sdk.ship import ShipInventory, Ship
import time
from straders_sdk.utils import set_logging, waypoint_slicer

BEHAVIOUR_NAME = "EXTRACT_AND_TRANSFER_OR_SELL_4"


class ExtractAndTransferOrSell_4(Behaviour):
    """Expects the following behaviour_params

    Optional:
    asteroid_wp: waypoint symbol to extract from
    cargo_to_transfer: list of cargo symbols to transfer to hauler"""

    def __init__(
        self,
        agent_name,
        ship_name,
        behaviour_params: dict = {},
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
        self.logger = logging.getLogger("bhvr_extract_and_transfer")

    def run(self):
        super().run()

        starting_credts = self.st.view_my_self().credits
        self.logger.info("NEEDLESS REQUEST - get inventory into DB")
        self.ship = ship = self.st.ships_view_one(self.ship_name, True)
        # self.st.ship_cooldown(ship)
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
            target_wp_sym = self.behaviour_params.get("asteroid_wp", None)
            if not target_wp_sym:
                target_wp = st.find_waypoints_by_type(
                    ship.nav.system_symbol, "ASTEROID_FIELD"
                )
                if target_wp:
                    target_wp_sym = target_wp[0].symbol
            if not target_wp_sym:
                raise AttributeError(
                    "Asteroid WP not set, no fallback asteroid fields found in current system"
                )
            target_sys_sym = waypoint_slicer(target_wp_sym)
        except AttributeError as e:
            self.logger.error("could not find waypoints because %s", e)
            self.logger.info("Triggering waypoint cache refresh. Rerun behaviour.")
            st.waypoints_view(ship.nav.system_symbol, True)
            return

        self.ship_extrasolar_jump(st.systems_view_one(target_sys_sym))
        self.ship_intrasolar(target_wp_sym)
        #
        #  - identify precious cargo materials - we will use surveys for these and transfer to hauler.
        #

        cargo_to_transfer = self.behaviour_params.get("cargo_to_transfer", [])
        if isinstance(cargo_to_transfer, str):
            cargo_to_transfer = [cargo_to_transfer]

        if cargo_to_transfer == []:
            self.logger.info("st.view_my_contracts() is triggering a needless request")
            contracts = st.view_my_contracts()
            if contracts:
                for contract in contracts:
                    if (not contract.accepted) or contract.fulfilled:
                        continue
                    for deliverable in contract.deliverables:
                        if deliverable.units_fulfilled < deliverable.units_required:
                            cargo_to_transfer.append(deliverable.symbol)

        if ship.can_survey:
            st.ship_survey(ship)
        cutoff_cargo_limit = None
        if ship.extract_strength > 0:
            cutoff_cargo_limit = ship.cargo_capacity - ship.extract_strength / 2
        self.extract_till_full(cargo_to_transfer, cutoff_cargo_limit)

        #
        # find a hauler from any of the matching agents.
        #

        refiners = self.find_refiners(ship.nav.waypoint_symbol)
        haulers = self.find_haulers(ship.nav.waypoint_symbol)
        for cargo in ship.cargo_inventory:
            if cargo.symbol in cargo_to_transfer:
                for hauler in refiners + haulers:
                    hauler: Ship
                    hauler_space = hauler.cargo_capacity - hauler.cargo_units_used

                    qty_to_transfer = min(
                        hauler.cargo_capacity - hauler.cargo_units_used, cargo.units
                    )
                    resp = st.ship_transfer_cargo(
                        ship,
                        cargo.symbol,
                        min(qty_to_transfer, hauler_space),
                        hauler.name,
                    )
                    if not resp:
                        st.ships_view_one(hauler.name, True)
                        self.logger.debug(
                            "Failed to transfer cargo to hauler %s %s",
                            hauler.name,
                            resp.error_code,
                        )
                    if resp:
                        break

        #
        # sell all remaining cargo now we're full note - if no haulers are around, might as well sell it - so no exclusions here.
        #
        self.sell_all_cargo()
        if ship.cargo_units_used == ship.cargo_capacity:
            self.logger.info("Ship unable to do anything, sleeping for 300s")
            time.sleep(300)

        #
        # end of script.
        #
        st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
        self.end()
        self.logger.info(
            "Completed. Credits: %s, change = %s",
            agent.credits,
            agent.credits - starting_credts,
        )

    def find_haulers(self, waypoint_symbol):
        haulers = self.find_adjacent_ships(waypoint_symbol, ["HAULER"])
        if len(haulers) == 0:
            haulers = self.find_adjacent_ships(waypoint_symbol, ["COMMAND"])
        return [hauler for hauler in haulers if hauler.cargo_space_remaining > 0]

    def find_refiners(self, waypoint_symbol):
        return self.find_adjacent_ships(waypoint_symbol, ["REFINERY"])


if __name__ == "__main__":
    set_logging(level=logging.DEBUG)
    agent_symbol = "CTRI-U-"
    ship_suffix = "5"
    params = {"asteroid_wp": "X1-GM20-77355E"}
    # params = {"asteroid_wp": "X1-JX88-51095C"}
    ExtractAndTransferOrSell_4(
        agent_symbol, f"{agent_symbol}-{ship_suffix}", params
    ).run()
