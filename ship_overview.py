from rich.console import RenderableType
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, ProgressBar
from textual.widget import Widget
from textual.reactive import Reactive
from textual.containers import ScrollableContainer, Container
from textual.css.query import NoMatches
from spacetraders_v2.spacetraders import SpaceTraders
from spacetraders_v2.ship import Ship
import json
import sys


class ShipPlate(Widget):
    ship: Ship = None
    display_text: Reactive = Reactive("loading...")

    def render(self) -> str:
        return self.display_text

    def __init__(
        self,
        ship,
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

    def update(self):
        pass


class ShipNamePlate(ShipPlate):
    def update(self, ship: Ship):
        self.ship = ship
        self.display_text = (
            f"{self.ship.name}\n{self.ship.frame.name}\n{self.ship.role}"
        )


class ShipNavPlate(ShipPlate):
    def update(self, ship: Ship):
        self.ship = ship
        self.display_text = f"{self.ship.nav.waypoint_symbol}\n{self.ship.nav.destination.x},{self.ship.nav.destination.y}\n{self.ship.nav.status}"


class ShipCargoPlate(ShipPlate):
    def update(self, ship: Ship):
        self.ship = ship
        self.display_text = (
            f"{self.ship.cargo_units_used} of {self.ship.cargo_capacity} \n" + f""
        )


class ShipCooldownPlate(ShipPlate):
    def update(self, ship: Ship):
        self.ship = ship
        if ship.name == "CTRI-4":
            pass
        self.display_text = f"{self.ship.nav.travel_time_remaining + self.ship.seconds_until_cooldown} seconds \ntill available"

    def visual_update(self):
        self.display_text = f"{self.ship.nav.travel_time_remaining + self.ship.seconds_until_cooldown} seconds \ntill available"


class ShipDetail(Static):
    ship: Ship = None
    name_plate: ShipNamePlate = None
    nav_plate: ShipNavPlate = None
    cargo_plate: ShipCargoPlate = None
    cooldown_plate: ShipCooldownPlate = None

    def __init__(
        self,
        ship: Ship,
        renderable: RenderableType = "",
        *,
        expand: bool = False,
        shrink: bool = False,
        markup: bool = True,
        name: str or None = None,
        id: str or None = None,
        classes: str or None = None,
        disabled: bool = False,
    ) -> None:
        self.ship = ship
        super().__init__(
            renderable,
            expand=expand,
            shrink=shrink,
            markup=markup,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )

    async def on_mount(self):
        self.name_plate = ShipNamePlate(self.ship)
        self.name_plate.ship = self.ship
        await self.mount(self.name_plate)
        self.nav_plate = ShipNavPlate(self.ship)
        self.nav_plate.ship = self.ship
        await self.mount(self.nav_plate)

        self.cargo_plate = ShipCargoPlate(self.ship)
        self.cargo_plate.ship = self.ship
        await self.mount(
            Container(
                self.cargo_plate,
                ProgressBar(id=f"{self.ship.name}_progressbar", show_eta=False),
            )
        )

        self.cooldown_plate = ShipCooldownPlate(self.ship)
        self.cooldown_plate.ship = self.ship
        await self.mount(self.cooldown_plate)

    def update(self, ship: Ship):
        self.ship = ship

        ship._check_cooldown()
        pb = self.query_one(f"#{self.ship.name}_progressbar")
        pb: ProgressBar
        pb.update(total=ship.cargo_capacity, progress=ship.cargo_units_used)
        self.name_plate.update(ship)
        self.nav_plate.update(ship)
        self.cargo_plate.update(ship)
        self.cooldown_plate.update(ship)


class ShipOverview(App):
    BINDINGS = [("r", "refresh", "Refresh ships")]
    CSS_PATH = "resources/overview.css"

    st: SpaceTraders = SpaceTraders()

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(id="ships_containers")
        yield Footer()

    async def action_refresh(self):
        for ship_id, ship in self.st.view_my_ships(True).items():
            await self.refresh_ship(ship_id, ship)

    async def action_visual_refresh(self):
        for ship_id in self.st.view_my_ships(True):
            ship_detail = self.query_one(f"#ship_{ship_id}")
            ship_detail: ShipDetail
            ship_detail.cooldown_plate.visual_update()

    async def refresh_ship(self, ship_id: str, ship: Ship):
        try:
            ship_detail = self.query_one(f"#ship_{ship_id}")
            ship_detail: ShipDetail
            ship_detail.update(ship)
        except NoMatches:
            ship_display = ShipDetail(ship, id=f"ship_{ship_id}")
            container = self.query_one("#ships_containers")
            await container.mount(ship_display)
            ship_display.update(ship)

    async def on_mount(self):
        self.load_st()
        self.st.view_my_ships()
        await self.action_refresh()
        self.set_interval(1, self.action_visual_refresh)
        self.set_interval(30, self.action_refresh)

    def load_st(self) -> SpaceTraders:
        agent_index = 0
        try:
            agent_index = int(sys.argv[1])
        except IndexError:
            pass
        try:
            user = json.load(open("user.json", "r"))
        except FileNotFoundError:
            print("No user.json found")
            exit()
        try:
            self.st.token = user["agents"][agent_index]["token"]
        except IndexError:
            print("No agents found")
            exit()


if __name__ == "__main__":
    ShipOverview().run()
