from dataclasses import dataclass
from datetime import datetime
from .utils import DATE_FORMAT


class symbol_class:
    symbol: str

    def __str__(self) -> str:
        return self.symbol


@dataclass
class Announement:
    id: int
    title: str
    body: str


@dataclass
class CrewInfo:
    pass


@dataclass
class FuelInfo:
    pass


@dataclass
class ShipRequirements:
    crew: int = 0
    modules: int = 0
    slots: int = 0


@dataclass
class ShipFrame(symbol_class):
    symbol: str
    name: str
    description: str
    module_slots: int
    mounting_points: int
    fuel_capacity: int
    condition: int
    requirements: ShipRequirements
    pass


@dataclass
class ShipModule:
    "represent a component installed within a ship"
    pass


@dataclass
class ShipMount:
    "represents a component mounted externally on a ship"
    pass


@dataclass
class ShipReactor(symbol_class):
    symbol: str
    name: str
    description: str
    condition: int
    power_output: int
    requirements: ShipRequirements
    pass


@dataclass
class ShipEngine(symbol_class):
    symbol: str
    name: str
    description: str
    condition: int
    speed: int
    requirements: ShipRequirements


@dataclass
class NavInfo:
    symbol: str
    type: str
    systemSymbol: str
    x: int
    y: int


@dataclass
class ShipRoute:
    origin: NavInfo
    destination: NavInfo
    departure_time: datetime
    arrival: datetime


@dataclass
class Agent(symbol_class):
    account_id: str
    symbol: str
    headquaters: str
    credits: int
    starting_faction: str

    @classmethod
    def from_json(cls, json_data: dict):
        return cls(*json_data.values())


@dataclass
class WaypointTrait(symbol_class):
    symbol: str
    name: str
    description: str


@dataclass
class Waypoint(symbol_class):
    system_symbol: str
    symbol: str
    type: str
    x: int
    y: int
    oribtals: list
    traits: list[WaypointTrait]
    chart: dict
    faction: dict

    @classmethod
    def from_json(cls, json_data: dict):
        rawobj = cls(*json_data.values())
        new_traits = []
        for old_trait in rawobj.traits:
            new_traits.append(WaypointTrait(*old_trait.values()))
        rawobj.traits = new_traits

        return rawobj


@dataclass
class ContractDeliverGood(symbol_class):
    symbol: str
    destination_symbol: str
    units_required: int
    units_fulfilled: int


# this should probably be its own thing
@dataclass
class Contract:
    id: str
    faction_symbol: str
    type: str
    deadline: datetime
    payment_upfront: int
    payment_completion: int
    deliver: list[ContractDeliverGood]
    accepted: bool
    fulfilled: bool
    expiration: datetime
    deadline_for_accept: datetime = None

    @classmethod
    def from_json(cls, json_data: dict):
        deadline = datetime.strptime(json_data["terms"]["deadline"], DATE_FORMAT)
        expiration = datetime.strptime(json_data["expiration"], DATE_FORMAT)

        deadline_to_accept = (
            datetime.strptime(json_data["deadlineToAccept"], DATE_FORMAT)
            if json_data["deadlineToAccept"] is not None
            else None
        )
        upfront = json_data["terms"]["payment"]["onAccepted"]
        on_success = json_data["terms"]["payment"]["onFulfilled"]
        deliveries = [
            ContractDeliverGood(*d.values())
            for d in json_data["terms"].get("deliver", [])
        ]

        return cls(
            json_data["id"],
            json_data["factionSymbol"],
            json_data["type"],
            deadline,
            upfront,
            on_success,
            deliveries,
            json_data["accepted"],
            json_data["fulfilled"],
            expiration,
            deadline_to_accept,
        )
