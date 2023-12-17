import sys

sys.path.append(".")
import logging
from behaviours.generic_behaviour import Behaviour
from straders_sdk.ship import ShipInventory, Ship
import time
from straders_sdk.utils import set_logging, waypoint_slicer

BEHAVIOUR_NAME = "EXTRACT_AND_FULFILL_7"


class ExtractAndFulfill_7(Behaviour):
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

        st = self.st
        self.ship = ship = st.ships_view_one(self.ship_name, True)
        self.st.ship_cooldown(ship)

        agent = st.view_my_self()

        #
        #  -- log beginning
        #

        if not ship.can_extract:
            st.logging_client.log_ending(
                BEHAVIOUR_NAME,
                ship.name,
                agent.credits,
                behaviour_params=self.behaviour_params,
            )
            return

        st.logging_client.log_beginning(BEHAVIOUR_NAME, ship.name, agent.credits)

        #
        # -- navigate to target waypoint - if not set, go for first asteroid field
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
            target_sys = st.systems_view_one(target_sys_sym)
        except AttributeError as e:
            self.logger.error("could not find waypoints because %s", e)
            self.logger.info("Triggering waypoint cache refresh. Rerun behaviour.")
            st.waypoints_view(ship.nav.system_symbol, True)
            self.end()
            return

        fulfil_wp = None
        fulfil_sys = None
        fulfil_wp_s = self.behaviour_params.get("fulfil_wp", None)
        if fulfil_wp_s:
            fulfil_wp = st.waypoints_view_one(target_sys_sym, fulfil_wp_s)
            fulfil_sys = st.systems_view_one(waypoint_slicer(fulfil_wp.symbol))

        self.ship_extrasolar(st.systems_view_one(target_sys_sym))
        self.ship_intrasolar(target_wp_sym)
        #
        #  - identify precious cargo materials - we will use surveys for these and transfer to hauler.
        #

        cargo_to_transfer = self.behaviour_params.get("cargo_to_transfer", [])
        if isinstance(cargo_to_transfer, str):
            cargo_to_transfer = [cargo_to_transfer]

        if ship.can_survey:
            st.ship_survey(ship)

        self.extract_till_full(cargo_to_transfer)

        # refresh the ship from the DB - ship possibly has received lots of cargo from other ships
        self.ship = st.ships_view_one(self.ship_name)

        if "MARKETPLACE" in target_wp[0].traits:
            self.sell_all_cargo(cargo_to_transfer)

        #
        # check remaining cargo after selling spillover
        #

        if ship.cargo_units_used > 0:
            if fulfil_sys:
                self.ship_extrasolar(fulfil_sys)
                self.ship_intrasolar(fulfil_wp.symbol)
                self.fulfil_any_relevant()
                self.sell_all_cargo()
            #
            else:
                self.logger.warning(
                    "no fulfillment system - behaviour params = %s",
                    self.behaviour_params,
                )

        # sell all remaining cargo now we're full note - if no haulers are around, might as well sell it - so no exclusions here.
        #
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
    from dispatcherWK12 import lock_ship

    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_suffix = sys.argv[2] if len(sys.argv) > 2 else "1"
    ship = f"{agent}-{ship_suffix}"
    params = {
        "fulfil_wp": "X1-CN90-22412Z",
        "asteroid_wp": "X1-CN90-02905X",
        "cargo_to_transfer": ["ALUMINUM_ORE"],
    }
    # params = {"asteroid_wp": "X1-JX88-51095C"}
    bhvr = ExtractAndFulfill_7(agent, f"{ship}", params)

    lock_ship(ship, "MANUAL", bhvr.connection, duration=120)
    set_logging(logging.DEBUG)
    bhvr.run()
    lock_ship(ship, "", bhvr.connection, duration=0)
