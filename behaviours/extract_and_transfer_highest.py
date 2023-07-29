from generic_behaviour import Behaviour
from spacetraders_v2.ship import ShipInventory, Ship

BEHAVIOUR_NAME = "EXTRACT_AND_TRANSFER"


class ExtractAndTransferHeighest(Behaviour):
    def __init__(self, client, ship, behaviour_params: dict = {}) -> None:
        self.st = client
        self.ship = ship
        self.behaviour_params = behaviour_params
        super().__init__()

    def run(self):
        ship = self.ship
        st = self.st
        agent = st.view_my_self()
        if not ship.can_extract:
            st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
            return

        st.logging_client.log_beginning(BEHAVIOUR_NAME, ship.name, agent.credits)

        target_wp_sym = self.behaviour_params.get("extract_waypoint", None)

        # a hauler has to be in position at the same waypoint as the extractor, and have enough space to accept the transfer

        self.ship_intrasolar(target_wp_sym)
        self.extract_till_full()

        if len(ship.cargo_inventory) == 0:
            st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)
            return
        largest_allocation = ShipInventory("", "", "", 0)
        for item in ship.cargo_inventory:
            if item.units > largest_allocation.units:
                largest_allocation = item

        for hauler in st.ships_view():
            hauler: Ship
            if hauler.nav.waypoint_symbol == target_wp_sym:
                if (
                    hauler.cargo_capacity - hauler.cargo_units_used
                    > largest_allocation.units
                ):
                    resp = st.ship_transfer_cargo(
                        ship,
                        largest_allocation.symbol,
                        largest_allocation.units,
                        hauler.name,
                    )

        st.logging_client.log_ending(BEHAVIOUR_NAME, ship.name, agent.credits)


if __name__ == "__main__":
    pass
