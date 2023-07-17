from .client_interface import SpaceTradersClient
from .responses import SpaceTradersResponse
from .utils import ApiConfig, _url, get_and_validate, post_and_validate
from .local_response import LocalSpaceTradersRespose
from .models import Waypoint, Survey
from .ship import Ship
import logging

logger = logging.getLogger(__name__)


class SpaceTradersApiClient:
    "implements SpaceTradersClient Protocol. No in-memory caching, no database, just the API."

    def __init__(self, token=None, base_url=None, version=None) -> None:
        self.token = token
        self.config = ApiConfig(base_url, version)
        pass

    def waypoints_view_one(
        self, system_symbol, waypoint_symbol, force=False
    ) -> Waypoint or SpaceTradersResponse:
        if waypoint_symbol == "":
            raise ValueError("waypoint_symbol cannot be empty")
        url = _url(f"systems/{system_symbol}/waypoints/{waypoint_symbol}")
        resp = get_and_validate(url, headers=self._headers())
        wayp = Waypoint.from_json(resp.data)
        if not resp:
            print(resp.error)
            return resp
        return wayp

    def waypoints_view(
        self, system_symbol: str
    ) -> dict[str:list] or SpaceTradersResponse:
        """view all waypoints in a system.

        Args:
            `system_symbol` (str): The symbol of the system to search for the waypoints in.

        Returns:
            Either a dict of Waypoint objects or a SpaceTradersResponse object on failure.
        """
        pass

        url = _url(f"systems/{system_symbol}/waypoints")
        resp = get_and_validate(url, headers=self._headers())
        if resp:
            new_wayps = {d["symbol"]: Waypoint.from_json(d) for d in resp.data}
            return new_wayps
        return resp

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def update(self, response_json: dict):
        pass

    def ship_orbit(self, ship: Ship):
        "my/ships/:miningShipSymbol/orbit thakes the ship name or the ship object"
        url = _url(f"my/ships/{ship.name}/orbit")
        if ship.nav.status == "IN_ORBIT":
            return LocalSpaceTradersRespose(None, 0, None, url=url)
        resp = post_and_validate(url, headers=self._headers())
        if resp:
            self.update(resp.data)
        return resp

    def ship_change_course(self, ship: Ship, dest_waypoint_symbol: str):
        "my/ships/:shipSymbol/course"
        url = _url(f"my/ships/{ship.name}/navigate")
        data = {"waypointSymbol": dest_waypoint_symbol}
        resp = post_and_validate(url, data, headers=self._headers())
        if resp:
            self.update(resp.data)
        return resp

    def ship_move(self, ship: Ship, dest_waypoint_symbol: str):
        "my/ships/:shipSymbol/navigate"

        #  4204{'message': 'Navigate request failed. Ship CTRI-4 is currently located at the destination.', 'code': 4204, 'data': {'shipSymbol': 'CTRI-4', 'destinationSymbol': 'X1-MP2-50435D'}}
        ship.orbit()
        url = _url(f"my/ships/{ship.name}/navigate")
        data = {"waypointSymbol": dest_waypoint_symbol}
        resp = post_and_validate(url, data, headers=self._headers())
        if resp:
            self.update(resp.data)
        return resp

    def ship_extract(self, ship: Ship, survey: Survey = None) -> SpaceTradersResponse:
        "/my/ships/{shipSymbol}/extract"

        url = _url(f"my/ships/{ship.name}/extract")
        if not ship.can_extract:
            return LocalSpaceTradersRespose("Ship cannot extract", 0, 4227, url=url)

        if ship.seconds_until_cooldown > 0:
            return LocalSpaceTradersRespose("Ship still on cooldown", 0, 4200, url=url)
        if ship.nav.status == "DOCKED":
            ship.orbit()
        data = survey.to_json() if survey is not None else None

        resp = post_and_validate(url, data=data, headers=self._headers())
        if resp:
            self.update(resp.data)
        return resp

    def ship_dock(self, ship: Ship):
        "/my/ships/{shipSymbol}/dock"
        url = _url(f"my/ships/{ship.name}/dock")

        if ship.nav.status == "DOCKED":
            return LocalSpaceTradersRespose(None, 200, None, url=url)
        resp = post_and_validate(url, headers=self._headers())
        if resp:
            self.update(resp.data)
        return resp

    def ship_refuel(self, ship: Ship):
        "/my/ships/{shipSymbol}/refuel"
        if ship.nav.status == "IN_ORBIT":
            ship.dock()
        if ship.nav.status != "DOCKED":
            ship.logger.error("Ship must be docked to refuel")

        url = _url(f"my/ships/{ship.name}/refuel")
        resp = post_and_validate(url, headers=self._headers())
        if resp:
            self.update(resp.data)
        return resp

    def ship_sell(self, ship: Ship, symbol: str, quantity: int):
        """/my/ships/{shipSymbol}/sell"""

        if ship.nav.status != "DOCKED":
            ship.dock()

        url = _url(f"my/ships/{ship.name}/sell")
        data = {"symbol": symbol, "units": quantity}
        resp = post_and_validate(url, data, headers=self._headers())
        if resp:
            self.update(resp.data)
        return resp

    def ship_survey(self, ship: Ship) -> list[Survey] or SpaceTradersResponse:
        "/my/ships/{shipSymbol}/survey"
        # 400, 4223, 'Ship survey failed. Ship must be in orbit to perform this type of survey.'
        if ship.nav.status == "DOCKED":
            ship.orbit()
        if not ship.can_survey:
            return LocalSpaceTradersRespose("Ship cannot survey", 0, 4240)
        if ship.seconds_until_cooldown > 0:
            return LocalSpaceTradersRespose("Ship still on cooldown", 0, 4000)
        url = _url(f"my/ships/{ship.name}/survey")
        resp = post_and_validate(url, headers=self._headers())

        self.update(resp.data)

        if resp:
            return [Survey.from_json(d) for d in resp.data.get("surveys", [])]
        return resp

    def ship_transfer_cargo(self, ship: Ship, trade_symbol, units, target_ship_name):
        "/my/ships/{shipSymbol}/transfer"

        # 4217{'message': 'Failed to update ship cargo. Cannot add 6 unit(s) to ship cargo. Exceeds max limit of 60.', 'code': 4217, 'data': {'shipSymbol': 'CTRI-1', 'cargoCapacity': 60, 'cargoUnits': 60, 'unitsToAdd': 6}}
        url = _url(f"my/ships/{ship.name}/transfer")
        data = {
            "tradeSymbol": trade_symbol,
            "units": units,
            "shipSymbol": target_ship_name,
        }
        resp = post_and_validate(url, data, headers=self._headers())
        self.update(resp.data)
        return resp
