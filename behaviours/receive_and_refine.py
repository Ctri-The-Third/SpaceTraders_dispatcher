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
import time

BEHAVIOUR_NAME = "RECEIVE_AND_REFINE"


class ReceiveAndRefine(Behaviour):
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

        #
        # travel to target site
        #
        did_something = False

        agent = st.view_my_self()
        st.logging_client.log_beginning(BEHAVIOUR_NAME, ship.name, agent.credits)

        start_wp_s = self.behaviour_params.get("asteroid_wp", ship.nav.waypoint_symbol)
        start_sys = st.systems_view_one(waypoint_slicer(start_wp_s))

        self.ship_extrasolar(start_sys, ship)
        self.ship_intrasolar(target_wp_symbol=start_wp_s)

        tradegood_symbols = {
            "IRON_ORE": "IRON",
            "ALUMINUM_ORE": "ALUMINUM",
            "COPPER_ORE": "COPPER",
        }

        #
        # do refinery
        #
        if ship.can_refine:
            # check for relevant cargo, if we've enough - condense.
            for cargo in ship.cargo_inventory:
                if cargo.symbol in tradegood_symbols and cargo.units >= 30:
                    self.sleep_until_ready()

                    resp = st.ship_refine(ship, tradegood_symbols[cargo.symbol])
                    if not resp:
                        self.logger.warning(
                            f"{ship.name} unable to refine %s because of %s",
                            cargo.symbol,
                            resp.error,
                        )
                        return
                    did_something = True

        valid_traders = []
        cargo_symbols = [cargo.symbol for cargo in ship.cargo_inventory]
        if any(
            cargo_symbol in tradegood_symbols.values() for cargo_symbol in cargo_symbols
        ):
            valid_traders = self.find_adjacent_ships(start_wp_s, ["HAULER"])
            for cargo in ship.cargo_inventory:
                if cargo.symbol in tradegood_symbols.values():
                    # check - is this hauler empty? does it already have this cargo?
                    for valid_trader in valid_traders:
                        if valid_trader.cargo_space_remaining == 0:
                            continue

                        # is the ship empty?
                        if valid_trader.cargo_units_used == 0:
                            resp = st.ship_transfer_cargo(
                                ship,
                                cargo.symbol,
                                min(cargo.units, valid_trader.cargo_capacity),
                                valid_trader.name,
                            )
                            if not resp:
                                self.logger.warning(
                                    f"{ship.name} unable to transfer %s because of %s",
                                    cargo.symbol,
                                    resp,
                                )
                                return
                            else:
                                did_something = True
                                break
                        else:
                            # if it's not empty, is there already some of this cargo there? (try not to mix)
                            valid_trader = st.ships_view_one(valid_trader.name, True)
                            self.logger.warning(
                                "Using a request here we don't have to - DB needs to cache inventory contents"
                            )
                            if cargo.symbol in [
                                cargo.symbol for cargo in valid_trader.cargo_inventory
                            ]:
                                resp = st.ship_transfer_cargo(
                                    ship,
                                    cargo.symbol,
                                    min(
                                        cargo.units, valid_trader.cargo_space_remaining
                                    ),
                                    valid_trader.name,
                                )
                                if not resp:
                                    self.logger.warning(
                                        f"{ship.name} unable to transfer %s because of %s",
                                        cargo.symbol,
                                        resp,
                                    )
                                    return
                                else:
                                    did_something = True
                                    break

        if not did_something:
            self.logger.debug("Nothing to do, sleeping for 60s")
            time.sleep(60)
        st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
        # if we've left over cargo to fulfill, fulfill it.
        # Not sure if it's more efficient to fill up the cargo hold and then fulfill, or to fulfill as we go.


if __name__ == "__main__":
    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "28"
    ship = f"{agent}-{ship_number}"
    behaviour_params = {"asteroid_wp": "X1-QB20-13975F"}
    bhvr = ReceiveAndRefine(agent, ship, behaviour_params or {})
    bhvr.run()
