from datetime import datetime
from .utils import DATE_FORMAT
from .models import CrewInfo, ShipFrame, FuelInfo, ShipModule, ShipMount
from .models import NavInfo, ShipReactor, ShipEngine, NavInfo, ShipRoute
from .models import ShipRequirements


class Ship:
    def __init__(self, json_data: dict) -> None:
        self.name: str = json_data["registration"]["name"]
        self.role: str = json_data["registration"]["role"]
        self.faction: str = json_data["registration"]["factionSymbol"]

        self.current_system: str = json_data["nav"]["systemSymbol"]
        self.current_waypoint: str = json_data["nav"]["waypointSymbol"]
        self.status: str = json_data["nav"]["status"]
        self.flight_mode: str = json_data["nav"]["flightMode"]

        # ---- ROUTE INFO  ----
        route = json_data["nav"]["route"]
        destination = NavInfo(
            route["destination"]["symbol"],
            route["destination"]["type"],
            route["destination"]["systemSymbol"],
            route["destination"]["x"],
            route["destination"]["y"],
        )
        departure = NavInfo(
            route["departure"]["symbol"],
            route["departure"]["type"],
            route["departure"]["systemSymbol"],
            route["departure"]["x"],
            route["departure"]["y"],
        )
        self.route = ShipRoute(
            departure,
            destination,
            datetime.strptime(route["arrival"], DATE_FORMAT),
            datetime.strptime(route["departureTime"], DATE_FORMAT),
        )

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

        # ---- ENGINE INFO ----
        engine_data: dict = json_data["engine"]
        engine_requirements = ShipRequirements(
            engine_data.get("requirements", {}).get("crew", 0),
            engine_data.get("requirements", {}).get("power", 0),
            engine_data.get("requirements", {}).get("slots", 0),
        )

        self.engine = ShipEngine(
            engine_data["symbol"],
            engine_data["name"],
            engine_data["description"],
            engine_data["condition"],
            engine_data["speed"],
            engine_requirements,
        )

        # ---- FUEL INFO ----

        self.fuel_capacity = json_data["fuel"]["capacity"]
        self.fuel_current = json_data["fuel"]["current"]
        self.fuel_consumed_history = json_data["fuel"]["consumed"]
        # needs expanded out into a class probably

        # ----  REACTOR INFO ----
        reactor_data: dict = json_data["reactor"]
        reactor_requirements = ShipRequirements(
            reactor_data.get("requirements", {}).get("crew", 0),
            reactor_data.get("requirements", {}).get("power", 0),
            reactor_data.get("requirements", {}).get("slots", 0),
        )
        self.reactor = ShipReactor(
            reactor_data["symbol"],
            reactor_data["name"],
            reactor_data["description"],
            reactor_data["condition"],
            reactor_data["powerOutput"],
            reactor_requirements,
        )

        # todo: modules and mounts
        self.modules = []
        self.mounts = []
        pass
