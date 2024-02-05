# takes a tradegood. Then trades that to ensure that the market is LIMITED
# if the export activity hits RESTRICTED, it switches to finding profitable import goods until that clears.

# script is happy to work to 0 profit, but will not work at a loss.


import time
import sys


sys.path.append(".")
from behaviours.generic_behaviour import Behaviour
import logging
from straders_sdk.ship import Ship
from straders_sdk.models import Market, Waypoint
from straders_sdk.utils import waypoint_slicer, set_logging, try_execute_select
from straders_sdk.constants import SUPPLY_LEVELS
from behaviours.generic_behaviour import Behaviour
import random

BEHAVIOUR_NAME = "EXPLORE_JUMPGATES"
SAFETY_PADDING = 180


class ExploreJumpgates(Behaviour):
    def __init__(
        self,
        agent_name,
        ship_name,
        behaviour_params: dict = ...,
        config_file_name="user.json",
        session=None,
    ) -> None:
        super().__init__(
            agent_name,
            ship_name,
            behaviour_params,
            config_file_name,
            session,
        )
        self.agent = self.st.view_my_self()
        self.logger = logging.getLogger(BEHAVIOUR_NAME)
        self.start_system = self.behaviour_params.get("start_system", None)

    def run(self):
        self.ship = self.st.ships_view_one(self.ship_name)
        self.sleep_until_ready()
        self.st.logging_client.log_beginning(
            BEHAVIOUR_NAME,
            self.ship.name,
            self.agent.credits,
            behaviour_params=self.behaviour_params,
        )
        self._run()
        self.end()

    def end(self):
        if self.ship:
            self.st.logging_client.log_ending(
                BEHAVIOUR_NAME, self.ship.name, self.st.view_my_self().credits
            )
        super().end()

    def default_params_obj(self):
        return_obj = super().default_params_obj()
        return_obj["start_system"] = "X1-SYST"
        return return_obj

    def _run(self):
        st = self.st
        ship = self.ship  # = st.ships_view_one(self.ship_name, True)
        ship: Ship
        agent = self.agent
        if not self.start_system:
            self.start_system = ship.nav.system_symbol
        current_gate = self.st.find_waypoints_by_type_one(
            self.start_system, "JUMP_GATE"
        )

        starting_gate, next_gate = self.find_uncharted_waypoints([current_gate.symbol])
        starting_gate_sys = self.st.systems_view_one(waypoint_slicer(starting_gate))

        if ship.nav.waypoint_symbol != starting_gate:
            arrived = self.ship_extrasolar_jump(starting_gate_sys.symbol)
            if not arrived:
                self.logger.error(f"Failed to jump to {starting_gate_sys.symbol}")
                st.sleep(SAFETY_PADDING)
                return
            arrived = self.ship_intrasolar(starting_gate)
            if not arrived:
                self.logger.error(f"Failed to navigate to {starting_gate}")
                st.sleep(SAFETY_PADDING)
                return
        self.st.ship_jump(ship, next_gate)
        self.st.ship_create_chart(ship)
        self.pathfinder.validate_and_refresh_jump_graph(starting_gate_sys, next_gate)
        self.sleep_until_ready()
        # find the jumpgate in the system

        # your code goes here

    def find_uncharted_waypoints(
        self, jumpgates_symbols: list[str], checked_symbols: list[str] = None
    ) -> tuple[str, str]:
        "returns a tuple of two waypoints, the second is the nearest uncharted waypoint - the first is the known link that leads to it."
        new_gates = []
        if not checked_symbols:
            checked_symbols = []
        # sort jumpgate_symbols randomly
        jumpgates_symbols.sort(key=lambda x: random.random())
        for gate in jumpgates_symbols:
            wayp = self.st.waypoints_view_one(gate)
            jumpgate = self.st.system_jumpgate(wayp)
            checked_symbols.append(gate)
            for connected_jumpgate in jumpgate.connected_waypoints:
                destination_wayp = self.st.waypoints_view_one(connected_jumpgate)
                # skip gates being built, we can't go there
                if destination_wayp.under_construction:
                    checked_symbols.append(connected_jumpgate)
                    continue
                destination = self.st.system_jumpgate(destination_wayp)
                if not destination:
                    return (gate, connected_jumpgate)
                if connected_jumpgate not in checked_symbols:
                    new_gates.append(connected_jumpgate)
        if new_gates:
            return self.find_uncharted_waypoints(new_gates, checked_symbols)


#
# to execute from commandline, run the script with the agent and ship_symbol as arguments, or edit the values below
#
if __name__ == "__main__":
    from dispatcherWK16 import lock_ship

    set_logging(level=logging.DEBUG)
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-U-"
    ship_number = sys.argv[2] if len(sys.argv) > 2 else "1"
    ship = f"{agent}-{ship_number}"
    behaviour_params = {
        "priority": 3,
    }

    bhvr = ExploreJumpgates(agent, ship, behaviour_params or {})

    lock_ship(ship, "MANUAL", 60 * 24)
    bhvr.run()
    lock_ship(ship, "MANUAL", 0)
