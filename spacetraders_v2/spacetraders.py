from .utils import get_and_validate, post_and_validate
from .responses import GameStatusResponse, SpaceTradersResponse, RegistrationResponse
from .responses import MyAgentResponse, ViewWaypointResponse, MyContractsResponse
from .responses import AcceptContractResponse, ViewWaypointsResponse
from .responses import AvailableShipsResponse, MyShipsResponse, PurchaseShipResponse
from .responses import ShipOrbitResponse, ShipNavigateResponse, ShipExtractResponse

from .models import Waypoint
from .ship import ShipyardShip, Ship

# Attempted relative import beyond top-level packagePylintE0402:relative-beyond-top-level


class SpaceTraders:
    """SpaceTraders API client."""

    ships: dict[str, Ship]
    waypoints: dict[str, Waypoint]

    def __init__(self, token=None, base_url=None, version=None) -> None:
        self.token = token
        self.base_url = "https://api.spacetraders.io" if base_url is None else base_url
        self.version = "v2" if version is None else version
        self.ships = {}
        self.waypoints = {}

        status = self.game_status()

        if not status:
            raise Exception(f"Could not connect to SpaceTraders server: {status.error}")
        pass

        self.announcements = status.announcements
        self.next_reset = status.next_reset

    def game_status(self) -> GameStatusResponse:
        """Get the status of the SpaceTraders game server."""
        url = self._url("")
        resp = get_and_validate(url)
        return GameStatusResponse(resp)

    def register(self, callsign, faction="COSMIC", email=None):
        """Register a new user."""
        url = self._url("register")
        data = {"symbol": callsign, "faction": faction}
        if email is not None:
            data["email"] = email
        resp = RegistrationResponse(post_and_validate(url, data))
        if resp:
            self.token = resp.token
        return resp

    def view_my_self(self):
        """view the current agent"""
        url = self._url("my/agent")
        resp = get_and_validate(url, headers=self._headers())

        return MyAgentResponse(resp)

    def view_my_ships(self):
        """view the current ships the agent has"""
        url = self._url("my/ships")
        resp = MyShipsResponse(get_and_validate(url, headers=self._headers()))

        new_ships = {ship.name: ship for ship in resp.ships}
        if resp:
            self.ships = self.ships | new_ships
        return resp

    def purchase_ship(self, waypoint: str or Waypoint, ship_type: str or ShipyardShip):
        """purchase a ship"""
        ship_type = ship_type.type if isinstance(ship_type, ShipyardShip) else ship_type
        waypoint = waypoint.symbol if isinstance(waypoint, Waypoint) else waypoint

        url = self._url("my/ships")
        data = {"shipType": ship_type, "waypointSymbol": waypoint}
        return PurchaseShipResponse(
            post_and_validate(url, data, headers=self._headers())
        )

    def view_my_contracts(self):
        """view the current contracts the agent has"""
        url = self._url("my/contracts")
        resp = get_and_validate(url, headers=self._headers())

        return MyContractsResponse(resp)

    def accept_contract(self, contract_id):
        """accept a contract"""
        url = self._url(f"my/contracts/{contract_id}/accept")
        resp = post_and_validate(url, headers=self._headers())

        return AcceptContractResponse(resp)

    # curl 'https://api.spacetraders.io/v2/systems/:systemSymbol/waypoints/:waypointSymbol' \
    def view_waypoint(self, system_symbol, waypoint_symbol):
        url = self._url(f"systems/{system_symbol}/waypoints/{waypoint_symbol}")
        resp = ViewWaypointResponse(get_and_validate(url, headers=self._headers()))
        self.waypoints[waypoint_symbol] = resp.waypoint

        return resp

    def view_waypoints(self, system_symbol: str) -> ViewWaypointsResponse:
        url = self._url(f"systems/{system_symbol}/waypoints")
        resp = ViewWaypointsResponse(get_and_validate(url, headers=self._headers()))

        self.waypoints = self.waypoints | {d.symbol: d for d in resp.waypoints}

        return resp

    def ship_orbit(self, ship_id: str):
        "my/ships/:miningShipSymbol/orbit"
        url = self._url(f"my/ships/{ship_id}/orbit")
        resp = post_and_validate(url, headers=self._headers())
        return ShipOrbitResponse(resp)

    def ship_move(self, ship_id: str, dest_waypoint_symbol: str):
        "my/ships/:shipSymbol/navigate"
        url = self._url(f"my/ships/{ship_id}/navigate")
        data = {"waypointSymbol": dest_waypoint_symbol}
        resp = post_and_validate(url, data, headers=self._headers())
        return ShipNavigateResponse(resp)

    def ship_extract(self, ship_id: str):
        "/my/ships/{shipSymbol}/extract"
        url = self._url(f"my/ships/{ship_id}/extract")
        resp = post_and_validate(url, headers=self._headers())
        return ShipExtractResponse(resp)

    def view_available_ships(self, waypoint: Waypoint) -> AvailableShipsResponse:
        url = self._url(
            f"systems/{waypoint.system_symbol}/waypoints/{waypoint.symbol}/shipyard"
        )
        resp = get_and_validate(url, headers=self._headers())
        return AvailableShipsResponse(resp)

    def _url(self, endpoint):
        return f"{self.base_url}/{self.version}/{endpoint}"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def find_waypoint_by_coords(self, system, x, y) -> Waypoint or None:
        for waypoint in self.waypoints.values():
            if waypoint.system_symbol == system and waypoint.x == x and waypoint.y == y:
                return waypoint
        return None
