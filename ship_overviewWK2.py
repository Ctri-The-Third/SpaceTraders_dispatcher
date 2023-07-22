from textual.app import App
from textual.widgets import Welcome, Header, Footer
from textual.containers import ScrollableContainer
from textual.widget import Widget
from spacetraders_v2 import SpaceTraders
from spacetraders_v2.ship import Ship
import json


class shipWidget(Widget):
    def __init__(
        self,
        ship: Ship,
        *children: Widget,
        name: str or None = None,
        id: str or None = None,
        classes: str or None = None,
        disabled: bool = False,
    ) -> None:
        self.ship = ship
        super().__init__(
            *children, name=name, id=id, classes=classes, disabled=disabled
        )

    def render(self):
        emojis = {"COMMAND": "👑", "EXCAVATOR": "⛏", "HAULER": "🚛", "SATELLITE": "📡"}
        out = f"{emojis[self.ship.role]} {self.ship.name} ({self.ship.nav.waypoint_symbol}) - {self.ship.cargo_units_used}/{self.ship.cargo_capacity} cargo used"
        return out


class ShipOverview(App):
    CSS_PATH = "resources/overviewwk2.css"

    def __init__(self, *args, **kwargs):
        self.st: SpaceTraders = kwargs.pop("st")
        super().__init__(*args, **kwargs)

        self.ships = self.st.ships_view()
        command_ships = {ship.name: ship for ship in self.ships.values() if ship.role == "COMMAND"}
        haulers = {ship.name: ship for ship in self.ships.values() if ship.role == "HAULER"}
        excavators = {ship.name: ship for ship in self.ships.values() if ship.role == "EXCAVATOR"}
        satellites = {ship.name: ship for ship in self.ships.values() if ship.role == "SATELLITE"}
        self.ships = command_ships | haulers | excavators | satellites
        pass

    def compose(self) -> None:
        ship_widgets = [shipWidget(ship, id=ship.name) for ship in self.ships.values()]
        yield Header("Ship Overview")

        yield ScrollableContainer(*ship_widgets)
        yield Footer()

    def on_button_pressed(self) -> None:
        self.exit()


if __name__ == "__main__":
    user = json.load(open("user.json"))
    st = SpaceTraders(
        user["agents"][0]["token"],
        db_host=user["db_host"],
        db_name=user["db_name"],
        db_user=user["db_user"],
        db_pass=user["db_pass"],
    )

    app = ShipOverview(st=st)
    app.run()
