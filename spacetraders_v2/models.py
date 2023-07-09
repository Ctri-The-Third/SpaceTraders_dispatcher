from dataclasses import dataclass
from datetime import datetime


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
class ShipFrame:
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
class ShipReactor:
    symbol: str
    name: str
    description: str
    condition: int
    power_output: int
    requirements: ShipRequirements
    pass


@dataclass
class ShipEngine:
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
    departure: NavInfo
    destination: NavInfo
    arrival: datetime
    departure_time: datetime


@dataclass
class Agent:
    account_id: str
    symbol: str
    headquaters: str
    credits: int
    starting_faction: str
