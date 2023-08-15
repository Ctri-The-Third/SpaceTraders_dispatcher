# This behaviour will go extrasoloar to the best place for a given item
#  then take it to the assigned location/ship and then transfer/sell the cargo


import sys

sys.path.append(".")
from straders_sdk.utils import waypoint_slicer, try_execute_select
from behaviours.generic_behaviour import Behaviour
import logging
import time


from straders_sdk.client_api import SpaceTradersApiClient as SpaceTraders

BEHAVIOUR_NAME = "RECEIVE_AND_FULFILL"
SAFETY_PADDING = 60


class BuyAndDeliverOrSell_6(Behaviour):
    """Requires a parameter blob containing

    `tradegood`: the symbol of the tradegood to buy\n
    `quantity`: the quantity to buy\n
    optional:\n
    `sell_wp`: if you want the ship to sell the cargo, set which waypoint\n
    `transfer_ship`: if you want the ship to transfer the cargo, set which ship\n
    `deliver_wp`: if you want the ship to deliver the cargo, set which waypoint"""

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

        #
        # setup initial parameters and preflight checks
        #
        if "tradegood" not in self.behaviour_params:
            time.sleep(SAFETY_PADDING)
            self.logger.error("No tradegood specified for ship %s", ship.name)
            raise ValueError("No tradegood specified for ship %s" % ship.name)
        if "quantity" not in self.behaviour_params:
            time.sleep(SAFETY_PADDING)
            self.logger.error("No quantity specified for ship %s", ship.name)
            raise ValueError("No quantity specified for ship %s" % ship.name)
        target_tradegood = self.behaviour_params["tradegood"]
        start_system = st.systems_view_one(ship.nav.system_symbol)
        max_to_buy = self.behaviour_params["quantity"]

        end_system = None
        end_waypoint = None
        receive_ship = None
        if "sell_wp" in self.behaviour_params:
            end_system = st.systems_view_one(
                waypoint_slicer(self.behaviour_params["sell_wp"])
            )
            end_waypoint = st.waypoints_view_one(
                end_system.symbol, self.behaviour_params["sell_wp"]
            )
        if "transfer_ship" in self.behaviour_params:
            receive_ship = st.ships_view_one(self.behaviour_params["transfer_ship"])
            end_system = receive_ship.nav.system_symbol

        target_waypoints = self.find_cheapest_markets_for_good(target_tradegood)

        if not target_waypoints:
            time.sleep(SAFETY_PADDING)
            self.logger.error("No waypoint found for tradegood %s", target_tradegood)
            raise ValueError("No waypoint found for tradegood %s" % target_tradegood)
        path = []
        for sym in target_waypoints:
            target_waypoint = st.waypoints_view_one(waypoint_slicer(sym), sym)
            target_system = st.systems_view_one(waypoint_slicer(sym))
            path = self.astar(self.graph, start_system, target_system)
            if path:
                break

        if not path:
            self.logger.error(
                "No jump gate route found to any of the markets that stock %s",
                target_tradegood,
            )
        # we're definitely in a jump gate system or we wouldn't have been able to do the astar routing.

        local_jumpgate = st.find_waypoints_by_type(start_system, "JUMP_GATE")[0]
        #
        # we know where we're going, we know what we're getting. Deployment.
        #

        self.ship_intrasolar(local_jumpgate.symbol)
        resp = self.ship_extrasolar(target_waypoint, path)
        self.ship_intrasolar(target_waypoint.symbol)

        st.ship_dock(ship)
        space = ship.cargo_capacity - ship.cargo_units_used

    def find_cheapest_markets_for_good(self, tradegood_sym: str) -> list[str]:
        sql = """select market_symbol from market_tradegood_listing
where symbol = %s
order by purchase_price asc """
        wayps = try_execute_select(self.connection, sql, (tradegood_sym,))

        if not wayps:
            self.logger.error(
                "Couldn't find cheapest market for good %s", tradegood_sym
            )
            return wayps
        return [wayp[0] for wayp in wayps]


if __name__ == "__main__":
    agent = sys.argv[1] if len(sys.argv) > 2 else "CTRI-VWK6A-"
    ship = sys.argv[2] if len(sys.argv) > 2 else "CTRI-VWK6A--1"
    bhvr = BuyAndDeliverOrSell_6(
        agent,
        ship,
        behaviour_params={
            "tradegood": "MODULE_ORE_REFINERY_I",
            "quantity": 9,
            "transfer_ship": "CTRI-UWK5--1",
        },
    )
    bhvr.run()
