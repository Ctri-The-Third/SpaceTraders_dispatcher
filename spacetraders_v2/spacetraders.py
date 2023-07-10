from .utils import get_and_validate, post_and_validate
from .responses import GameStatusResponse, SpaceTradersResponse, RegistrationResponse
from .responses import MyAgentResponse, ViewWaypointResponse, MyContractsResponse
from .responses import AcceptContractResponse, ViewWaypointsResponse
from .responses import AvailableShipsResponse

from .models import Waypoint

# Attempted relative import beyond top-level packagePylintE0402:relative-beyond-top-level


class SpaceTraders:
    """SpaceTraders API client."""

    def __init__(self, token=None, base_url=None, version=None) -> None:
        self.token = token
        self.base_url = "https://api.spacetraders.io" if base_url is None else base_url
        self.version = "v2" if version is None else version

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
        resp = get_and_validate(url, headers=self._headers())

        return ViewWaypointResponse(resp)

    def view_waypoints(self, system_symbol):
        url = self._url(f"systems/{system_symbol}/waypoints")
        resp = get_and_validate(url, headers=self._headers())

        return ViewWaypointsResponse(resp)

    def view_available_ships(
        self, waypoint: Waypoint, system_symbol=None, shipyard_wp_symbol=None
    ):
        if waypoint:
            system_symbol = waypoint.system_symbol
            shipyard_wp_symbol = waypoint.symbol
        elif not system_symbol and shipyard_wp_symbol:
            system_symbol = shipyard_wp_symbol[0:6]
            pass
        elif not shipyard_wp_symbol:
            raise ValueError(
                "Must provide a waypoint or system_symbol and shipyard_wp_symbol"
            )

        url = self._url(
            f"systems/{system_symbol}/waypoints/{shipyard_wp_symbol}/shipyard"
        )
        resp = get_and_validate(url, headers=self._headers())
        return AvailableShipsResponse(resp)
        return resp

    def _url(self, endpoint):
        return f"{self.base_url}/{self.version}/{endpoint}"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}
