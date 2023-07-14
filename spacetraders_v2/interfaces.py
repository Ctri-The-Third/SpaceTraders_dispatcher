from typing import Protocol
from .models import Nav, ShipFrame, ShipEngine, ShipReactor


class Ship(Protocol):
    name: str
    role: str
    faction: str

    nav: Nav
    frame: ShipFrame
    reactor: ShipReactor
    engine: ShipEngine
    # ------------------
    # ---- CREW INFO ----
    crew_capacity: int
    crew_current: int
    crew_required: int
    crew_rotation: str
    crew_morale: int
    crew_wages: int

    cargo_capacity: int
    cargo_units_used: int
    cargo_inventory: list

    # ---- FUEL INFO ----
    fuel_capacity: int
    fuel_current: int
    fuel_consumed_history: list

    # ----  REACTOR INFO ----

    # todo: modules and mounts
    modules: list
    mounts: list
