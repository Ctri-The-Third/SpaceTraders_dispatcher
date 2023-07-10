from datetime import datetime
from .utils import DATE_FORMAT
from .models import CrewInfo, ShipFrame, FuelInfo, ShipModule, ShipMount
from .models import RouteNode, ShipReactor, ShipEngine, RouteNode, ShipRoute
from .models import ShipRequirements, Nav


class Ship:
    def __init__(self, json_data: dict) -> None:
        self.name: str = json_data.get("registration", {}).get("name", "")
        self.role: str = json_data["registration"]["role"]
        self.faction: str = json_data["registration"]["factionSymbol"]

        self.nav = Nav.from_json(json_data["nav"])

        self.frame = _frame_from_json(json_data["frame"])
        self.reactor = _reactor_from_json(json_data["reactor"])
        self.engine = _engine_from_json(json_data["engine"])

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
        self.cargo_inventory: list = json_data["cargo"]["inventory"]

        # ---- FUEL INFO ----

        self.fuel_capacity = json_data["fuel"]["capacity"]
        self.fuel_current = json_data["fuel"]["current"]
        self.fuel_consumed_history = json_data["fuel"]["consumed"]
        # needs expanded out into a class probably

        # ----  REACTOR INFO ----

        # todo: modules and mounts
        self.modules = []
        self.mounts = []
        pass

    @classmethod
    def from_json(cls, json_data: dict):
        return cls(json_data)


class ShipyardShip:
    def __init__(self, json_data: dict) -> None:
        self.frame = _frame_from_json(json_data["frame"])
        self.reactor = _reactor_from_json(json_data["reactor"])
        self.engine = _engine_from_json(json_data["engine"])
        self.name = json_data["name"]
        self.description = json_data["description"]
        self.type = json_data["type"]
        self.purchase_price = json_data["purchasePrice"]
        # ------------------
        # ---- CREW INFO ----

        # needs expanded out into a class probably

        # ----  REACTOR INFO ----

        # todo: modules and mounts
        self.modules = []
        self.mounts = []
        pass

    @classmethod
    def from_json(cls, json_data: dict):
        return cls(json_data)


def _reactor_from_json(json_data: dict) -> ShipReactor:
    reactor_requirements = ShipRequirements(
        json_data.get("requirements", {}).get("crew", 0),
        json_data.get("requirements", {}).get("power", 0),
        json_data.get("requirements", {}).get("slots", 0),
    )
    return ShipReactor(
        json_data["symbol"],
        json_data["name"],
        json_data["description"],
        json_data.get("condition", 0),
        json_data["powerOutput"],
        reactor_requirements,
    )


def _engine_from_json(json_data: dict) -> ShipEngine:
    engine_requirements = ShipRequirements(
        json_data.get("requirements", {}).get("crew", 0),
        json_data.get("requirements", {}).get("power", 0),
        json_data.get("requirements", {}).get("slots", 0),
    )
    return ShipEngine(
        json_data["symbol"],
        json_data["name"],
        json_data["description"],
        json_data.get("condition", 0),
        json_data["speed"],
        engine_requirements,
    )


def _frame_from_json(json_data: dict) -> ShipFrame:
    frame_requirements = ShipRequirements(
        json_data.get("requirements", {}).get("crew", 0),
        json_data.get("requirements", {}).get("power", 0),
        json_data.get("requirements", {}).get("slots", 0),
    )
    frame = ShipFrame(
        json_data["symbol"],
        json_data["name"],
        json_data["description"],
        json_data["moduleSlots"],
        json_data["mountingPoints"],
        json_data["fuelCapacity"],
        json_data.get("condition", 0),
        frame_requirements,
    )
    return frame
