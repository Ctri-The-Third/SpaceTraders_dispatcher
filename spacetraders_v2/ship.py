from datetime import datetime, timedelta
from dataclasses import dataclass
from .models import CrewInfo, ShipFrame, FuelInfo, ShipModule, ShipMount
from .models import RouteNode, ShipReactor, ShipEngine, RouteNode, ShipRoute
from .models import ShipRequirements, Nav, Survey, Deposit
from .client_interface import SpaceTradersInteractive, SpaceTradersClient
from .client_stub import SpaceTradersStubClient
from .responses import SpaceTradersResponse
from .local_response import LocalSpaceTradersRespose
import logging
from .utils import parse_timestamp, get_and_validate, post_and_validate, _url
from .utils import SURVEYOR_SYMBOLS

from .responses import SpaceTradersResponse


### the question arises - if the Ship class is to have methods that interact with the server, which pattern do we use to implement that.
# choice - pass in a REFERENCE to the SpaceTraders class (which is kinda like a "session") -
#     example: https://github.com/cosmictraders/autotraders/blob/master/autotraders/space_traders_entity.py
#   - advantages = simple. if there's a st object we can just call, then everything becomes simple.
#   - disadvantage = we're creating a circle. the ST gets ships, ships call ST. It feels wrong.
#   - disadvantage = I feel the term dependency injection applies here? I need to research if that's inherently bad.
#
# choice - make Ship and ST alike inherit from a "client" class that has the token, and underlying generic methods that interact with the server.
#   - advantage = no circular dependency, code already exists.
#   - disadvantage = more complex, greater refactor, higher risk of me getting bored.
#
# what I read:
# * https://medium.com/@suneandreasdybrodebel/pythonic-dependency-injection-a-practical-guide-83a1b1299280
#   - I am absolutely not writing abstractions for everything, too much effort, low payoff, high chance of burnout
# * https://softwareengineering.stackexchange.com/questions/393065/can-we-completely-replace-inheritance-using-strategy-pattern-and-dependency-inje
# * https://www.thoughtworks.com/insights/blog/composition-vs-inheritance-how-choose
#   - this reminded me of the python `Protocol` thing I read about recently.
# protocols  https://andrewbrookins.com/technology/building-implicit-interfaces-in-python-with-protocol-classes/
#   - protocols appear to be the python equivelant of interfaces, which I'm avoiding.
# DECISION: second option, a "client" class that has the token, and underlying generic methods that interact with the server

# COMPLICATION: Circular imports, because SpaceTraders loads Ships, which loads responses, which loads ships.

# COUPLE-DAYS-LATER SOLUTION: I also ended up making an abstract response class after all, enables sending error "responses" locally without calling the API


@dataclass
class ShipInventory:
    symbol: str
    name: str
    description: str
    units: int

    @classmethod
    def from_json(cls, json_data: dict):
        return cls(*json_data.values())


class Ship(SpaceTradersInteractive):
    def __init__(
        self,
        json_data: dict,
        client: SpaceTradersClient,
        parent: SpaceTradersInteractive = None,
    ) -> None:
        self._parent = parent if parent is not None else SpaceTradersStubClient()
        self.client = client
        self.logger = logging.getLogger("ship-logger")
        self.name: str = json_data.get("registration", {}).get("name", "")
        self.role: str = json_data["registration"]["role"]
        self.faction: str = json_data["registration"]["factionSymbol"]

        self.nav = Nav.from_json(json_data["nav"])

        self.frame = ShipFrame.from_json(json_data["frame"])
        self.reactor = ShipReactor.from_json(json_data["reactor"])
        self.engine = ShipEngine.from_json(json_data["engine"])

        # ------------------
        # ---- CREW INFO ----
        self.crew_capacity: int = json_data["crew"]["capacity"]
        self.crew_current: int = json_data["crew"]["current"]
        self.crew_required: int = json_data["crew"]["required"]
        self.crew_rotation: str = json_data["crew"]["rotation"]
        self.crew_morale: int = json_data["crew"]["morale"]
        self.crew_wages: int = json_data["crew"]["wages"]

        self.cargo_capacity: int = json_data["cargo"]["capacity"]
        self.cargo_units_used: int = json_data["cargo"]["units"]
        self.cargo_inventory: list[ShipInventory] = [
            ShipInventory.from_json(d) for d in json_data["cargo"]["inventory"]
        ]

        # ---- FUEL INFO ----

        self.fuel_capacity = json_data["fuel"]["capacity"]
        self.fuel_current = json_data["fuel"]["current"]
        self.fuel_consumed_history = json_data["fuel"]["consumed"]
        # needs expanded out into a class probably

        self._cooldown = None
        # ----  REACTOR INFO ----

        # todo: modules and mounts
        self.modules: list[ShipModule] = [ShipModule(d) for d in json_data["modules"]]
        self.mounts: list[ShipMount] = [ShipMount(d) for d in json_data["mounts"]]

        pass

    @property
    def can_survey(self) -> bool:
        for surveyor in SURVEYOR_SYMBOLS:
            if surveyor in [d.symbol for d in self.mounts]:
                return True
        return False

    @property
    def can_extract(self) -> bool:
        extractors = [
            "MOUNT_MINING_LASER_I",
            "MOUNT_MINING_LASER_II",
            "MOUNT_MINING_LASER_III",
        ]
        for extractor in extractors:
            if extractor in [d.symbol for d in self.mounts]:
                return True
        return False

    @classmethod
    def from_json(
        cls,
        json_data: dict,
        client: SpaceTradersClient,
        parent: SpaceTradersInteractive = None,
    ):
        return cls(json_data, client=client, parent=parent)

    def orbit(self):
        """my/ships/:miningShipSymbol/orbit takes the ship name or the ship object"""
        if self.nav.status == "DOCKED":
            return self.client.ship_orbit(self)
        return LocalSpaceTradersRespose(None, 0, None, "")

    def change_course(self, ship, dest_waypoint_symbol: str):
        """my/ships/:shipSymbol/course"""
        upd = self.client.ship_change_course(self, dest_waypoint_symbol)
        return upd

    def move(self, dest_waypoint_symbol: str):
        """my/ships/:shipSymbol/navigate"""

        if self.nav.waypoint_symbol == dest_waypoint_symbol:
            return LocalSpaceTradersRespose(
                f"Navigate request failed, Ship '{self.name}' is already at the destination'",
                0,
                None,
                "ship.move()",
            )
        if self.nav.status == "DOCKED":
            self.orbit()

        upd = self.client.ship_move(self, dest_waypoint_symbol)
        return upd

    def extract(self, survey: Survey = None) -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/extract"""
        if self.nav.status != "IN_ORBIT":
            self.orbit()
        upd = self.client.ship_extract(self, survey)
        return upd

    def dock(self):
        """/my/ships/{shipSymbol}/dock"""
        upd = self.client.ship_dock(self)
        return upd

    def refuel(self):
        """/my/ships/{shipSymbol}/refuel"""
        upd = self.client.ship_refuel(self)
        return upd

    def sell(self, symbol: str, quantity: int):
        """/my/ships/{shipSymbol}/sell"""
        if self.nav.status != "DOCKED":
            self.client.ship_dock(self)
        upd = self.client.ship_sell(self, symbol, quantity)
        return upd

    def survey(self) -> list[Survey] or SpaceTradersResponse:
        """/my/ships/{shipSymbol}/survey"""
        upd = self.client.ship_survey(self)
        return upd

    def transfer_cargo(self, trade_symbol, units, target_ship_name):
        """/my/ships/{shipSymbol}/transfer"""
        upd = self.client.ship_transfer_cargo(
            self, trade_symbol, units, target_ship_name
        )
        return upd

    def receive_cargo(self, trade_symbol, units):
        for inventory_item in self.cargo_inventory:
            if inventory_item.symbol == trade_symbol:
                inventory_item.units += units
                return
        self.cargo_inventory.append(
            ShipInventory(
                trade_symbol,
                "this string came from receive cargo, shouldn't wind up in DB",
                "this string came from receive cargo, shouldn't wind up in DB",
                units,
            )
        )

    def force_update(self):
        # /my/ships/{shipSymbol}
        url = _url(f"my/ships/{self.name}")
        resp = get_and_validate(url, headers=self._headers())
        self.update(resp.data)
        return resp

    def update(self, ship_data: dict):
        if ship_data is None:
            return

        if isinstance(ship_data, dict):
            if "nav" in ship_data:
                self.nav = Nav.from_json(ship_data["nav"])
            if "cargo" in ship_data:
                self.cargo_capacity = ship_data["cargo"]["capacity"]
                self.cargo_units_used = ship_data["cargo"]["units"]
                self.cargo_inventory: list[ShipInventory] = [
                    ShipInventory.from_json(d) for d in ship_data["cargo"]["inventory"]
                ]
            if "cooldown" in ship_data:
                self._cooldown = parse_timestamp(ship_data["cooldown"]["expiration"])
                if self.seconds_until_cooldown > 6000:
                    self.logger.warning("Cooldown is over 100 minutes")
            if "fuel" in ship_data:
                self.fuel_capacity = ship_data["fuel"]["capacity"]
                self.fuel_current = ship_data["fuel"]["current"]
                self.fuel_consumed_history = ship_data["fuel"]["consumed"]
        # pass the updated ship to the client to be logged appropriately

    @property
    def seconds_until_cooldown(self) -> timedelta:
        if not self._cooldown:
            self.client.ship_cooldown(self)
        time_to_wait = self._cooldown - datetime.utcnow()
        seconds = max(time_to_wait.seconds + (time_to_wait.days * 86400), 0)
        if seconds > 6000:
            self.logger.warning("Cooldown is over 100 minutes")
        return seconds
