from datetime import datetime, timedelta
from dataclasses import dataclass
import pytz
from .models import CrewInfo, ShipFrame, FuelInfo, ShipModule, ShipMount
from .models import RouteNode, ShipReactor, ShipEngine, RouteNode, ShipRoute
from .models import ShipRequirements, Nav, Survey, Deposit
from .client import SpaceTradersClient
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


class Ship(SpaceTradersClient):
    def __init__(
        self,
        json_data: dict,
        parent: SpaceTradersClient = None,
        token: str = None,
    ) -> None:
        if token:
            self.token = token
        elif parent:
            self.token = parent.token
        else:
            raise ValueError("No token provided")
        self._parent = parent
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
    def from_json(cls, json_data: dict):
        return cls(json_data, token="")

    def orbit(self):
        "my/ships/:miningShipSymbol/orbit thakes the ship name or the ship object"
        url = _url(f"my/ships/{self.name}/orbit")
        if self.nav.status == "IN_ORBIT":
            return LocalSpaceTradersRespose(None, 0, None, url=url)
        resp = post_and_validate(url, headers=self._headers())
        self.update(resp.data)
        return resp

    def change_course(self, dest_waypoint_symbol: str):
        "my/ships/:shipSymbol/course"
        url = _url(f"my/ships/{self.name}/navigate")
        data = {"waypointSymbol": dest_waypoint_symbol}
        resp = post_and_validate(url, data, headers=self._headers())
        self.update(resp.data)
        return resp

    def move(self, dest_waypoint_symbol: str):
        "my/ships/:shipSymbol/navigate"

        #  4204{'message': 'Navigate request failed. Ship CTRI-4 is currently located at the destination.', 'code': 4204, 'data': {'shipSymbol': 'CTRI-4', 'destinationSymbol': 'X1-MP2-50435D'}}
        self.orbit()
        url = _url(f"my/ships/{self.name}/navigate")
        data = {"waypointSymbol": dest_waypoint_symbol}
        resp = post_and_validate(url, data, headers=self._headers())
        self.update(resp.data)
        return resp

    def extract(self, survey: Survey = None) -> SpaceTradersResponse:
        "/my/ships/{shipSymbol}/extract"

        url = _url(f"my/ships/{self.name}/extract")
        if not self.can_extract:
            return LocalSpaceTradersRespose("Ship cannot extract", 0, 4227, url=url)

        if self.seconds_until_cooldown > 0:
            return LocalSpaceTradersRespose("Ship still on cooldown", 0, 4200, url=url)
        if self.nav.status == "DOCKED":
            self.orbit()
        data = survey.to_json() if survey is not None else None

        resp = post_and_validate(url, data=data, headers=self._headers())
        self.update(resp.data)
        return resp

    def dock(self):
        "/my/ships/{shipSymbol}/dock"
        url = _url(f"my/ships/{self.name}/dock")

        if self.nav.status == "DOCKED":
            return LocalSpaceTradersRespose(None, 200, None, url=url)
        resp = post_and_validate(url, headers=self._headers())
        self.update(resp.data)
        return resp

    def refuel(self):
        "/my/ships/{shipSymbol}/refuel"
        if self.nav.status == "IN_ORBIT":
            self.dock()
        if self.nav.status != "DOCKED":
            self.logger.error("Ship must be docked to refuel")

        url = _url(f"my/ships/{self.name}/refuel")
        resp = post_and_validate(url, headers=self._headers())
        self.update(resp.data)
        return resp

    def sell(self, symbol: str, quantity: int):
        """/my/ships/{shipSymbol}/sell"""

        if self.nav.status != "DOCKED":
            self.dock()

        url = _url(f"my/ships/{self.name}/sell")
        data = {"symbol": symbol, "units": quantity}
        resp = post_and_validate(url, data, headers=self._headers())
        self.update(resp.data)
        return resp

    def survey(self) -> list[Survey] or SpaceTradersResponse:
        "/my/ships/{shipSymbol}/survey"
        # 400, 4223, 'Ship survey failed. Ship must be in orbit to perform this type of survey.'
        if self.nav.status == "DOCKED":
            self.orbit()
        if not self.can_survey:
            return LocalSpaceTradersRespose("Ship cannot survey", 0, 4240)
        if self.seconds_until_cooldown > 0:
            return LocalSpaceTradersRespose("Ship still on cooldown", 0, 4000)
        url = _url(f"my/ships/{self.name}/survey")
        resp = post_and_validate(url, headers=self._headers())
        self.update(resp.data)

        if resp:
            return [Survey.from_json(d) for d in resp.data.get("surveys", [])]
        return resp

    def transfer_cargo(self, trade_symbol, units, target_ship_name):
        "/my/ships/{shipSymbol}/transfer"

        # 4217{'message': 'Failed to update ship cargo. Cannot add 6 unit(s) to ship cargo. Exceeds max limit of 60.', 'code': 4217, 'data': {'shipSymbol': 'CTRI-1', 'cargoCapacity': 60, 'cargoUnits': 60, 'unitsToAdd': 6}}
        url = _url(f"my/ships/{self.name}/transfer")
        data = {
            "tradeSymbol": trade_symbol,
            "units": units,
            "shipSymbol": target_ship_name,
        }
        resp = post_and_validate(url, data, headers=self._headers())
        self.update(resp.data)
        return resp

    def _check_cooldown(self):
        # /my/ships/{shipSymbol}/cooldown
        url = _url(f"my/ships/{self.name}/cooldown")
        resp = get_and_validate(url, headers=self._headers())
        if resp and "expiration" in resp.data:
            self.update({"cooldown": resp.data})
        else:
            self._cooldown = datetime.utcnow()

    def force_update(self):
        # /my/ships/{shipSymbol}
        url = _url(f"my/ships/{self.name}")
        resp = get_and_validate(url, headers=self._headers())
        self.update(resp.data)
        return resp

    def update(self, ship_data: dict):
        if ship_data is None:
            return
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
        if self._parent is not None:
            self._parent.update(ship_data)

    @property
    def seconds_until_cooldown(self) -> timedelta:
        if not self._cooldown:
            self._check_cooldown()
        time_to_wait = self._cooldown - datetime.utcnow()
        seconds = max(time_to_wait.seconds + (time_to_wait.days * 86400), 0)
        if seconds > 6000:
            self.logger.warning("Cooldown is over 100 minutes")
        return seconds
