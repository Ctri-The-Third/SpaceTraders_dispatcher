from typing import Protocol, runtime_checkable
from .models import Waypoint, Survey, Market, Shipyard
from .ship import Ship

from .responses import SpaceTradersResponse
import psycopg2
import uuid
import json


class SpaceTradersPostgresLoggerClient:
    token: str = None

    def __init__(
        self, token, db_host, db_port, db_name, db_user, db_pass, current_agent_name=""
    ) -> None:
        self.token = token
        self.connection = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_pass,
        )
        self.session_id = str(uuid.uuid4())
        self.connection.autocommit = True
        self.current_agent_name = ""

    pass

    def log_beginning(self, behaviour_name: str, starting_credits=None):
        sql = """INSERT INTO public.logging( event_name, event_timestamp, agent_name, ship_name, session_id, endpoint_name, new_credits, status_code, error_code, event_params)
        values (%s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s);"""
        cursor = self.connection.cursor()
        cursor.execute(
            sql,
            (
                "SCRIPT_START",
                "GLOBAL",
                self.current_agent_name,
                self.session_id,
                None,
                starting_credits,
                200,
                0,
                json.dumps({"script_name": behaviour_name}),
            ),
        )

    def log_event(
        self,
        event_name,
        ship_name,
        endpoint_name: str = None,
        response_obj=None,
        event_params={},
    ) -> dict:
        error_code = 0
        status_code = 0
        new_credits = None
        if response_obj is not None:
            if isinstance(response_obj, SpaceTradersResponse):
                status_code = response_obj.status_code
                error_code = response_obj.error_code
                credits = (
                    response_obj.response_json.get("data", {})
                    .get("agent", {})
                    .get("credits", None)
                )
                if credits:
                    new_credits = credits

            elif isinstance(response_obj, (Ship, Waypoint, Market, Shipyard)):
                status_code = 200

        if isinstance(ship_name, Ship):
            ship_name = ship_name.name
        sql = """INSERT INTO public.logging(
	event_name, event_timestamp, agent_name, ship_name, session_id, endpoint_name, new_credits, status_code, error_code, event_params)
	VALUES (%s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s);"""

        cursor = self.connection.cursor()
        cursor.execute(
            sql,
            (
                event_name,
                self.current_agent_name,
                ship_name,
                self.session_id,
                endpoint_name,
                new_credits,
                status_code,
                error_code,
                json.dumps(event_params),
            ),
        )
        pass

    def update(self, update_obj: SpaceTradersResponse):
        return

    def waypoints_view(
        self, system_symbol: str, response=None
    ) -> dict[str:list] or SpaceTradersResponse:
        """view all waypoints in a system. Uses cached values by default.

        Args:
            `system_symbol` (str): The symbol of the system to search for the waypoints in.

        Returns:
            Either a dict of Waypoint objects or a SpaceTradersResponse object on failure.
        """
        endpoint = f"systems/{system_symbol}/waypoints/"
        self.log_event("waypoints_view", "GLOBAL", endpoint, response)

    def waypoints_view_one(
        self, system_symbol, waypoint_symbol, force=False
    ) -> Waypoint or SpaceTradersResponse:
        """view a single waypoint in a system. Uses cached values by default.

        Args:
            `system_symbol` (str): The symbol of the system to search for the waypoint in.
            `waypoint_symbol` (str): The symbol of the waypoint to search for.
            `force` (bool): Optional - Force a refresh of the waypoint. Defaults to False.

        Returns:
            Either a Waypoint object or a SpaceTradersResponse object on failure."""

        endpoint = f"systems/{system_symbol}/waypoints/{waypoint_symbol}"
        self.log_event("waypoints_view", "GLOBAL", endpoint)

        pass

    def find_waypoint_by_coords(
        self, system_symbol: str, x: int, y: int
    ) -> Waypoint or SpaceTradersResponse:
        # don't log anything, not an API call
        pass

    def find_waypoints_by_trait(
        self, system_symbol: str, trait: str
    ) -> list[Waypoint] or SpaceTradersResponse:
        # don't log anything, not an API call

        pass

    def find_waypoints_by_trait_one(
        self, system_symbol: str, trait: str
    ) -> Waypoint or SpaceTradersResponse:
        # don't log anything, not an API call

        pass

    def find_waypoint_by_type(
        self, system_wp, waypoint_type
    ) -> Waypoint or SpaceTradersResponse:
        # don't log anything, not an API call
        pass

    def ship_orbit(self, ship, response=None) -> SpaceTradersResponse:
        url = _url(f"my/ships/:ship_name/orbit")
        self.log_event("ship_orbit", ship.name, url, response)
        pass

    def ship_change_course(
        self, ship: "Ship", dest_waypoint_symbol: str, response=None
    ):
        """my/ships/:shipSymbol/course"""
        url = _url(f"my/ships/:ship_name/navigate")
        self.log_event("ship_change_course", ship.name, url, response)
        pass

    def ship_move(
        self, ship: "Ship", dest_waypoint_symbol: str, response=None
    ) -> SpaceTradersResponse:
        """my/ships/:shipSymbol/navigate"""
        url = _url(f"my/ships/:ship_name/navigate")
        self.log_event("ship_move", ship.name, url, response)

        pass

    def ship_extract(
        self, ship: "Ship", survey: Survey = None, response=None
    ) -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/extract"""
        url = _url(f"my/ships/:ship_name/extract")
        self.log_event("ship_extract", ship.name, url, response)
        pass

    def ship_dock(self, ship: "Ship", response=None) -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/dock"""
        url = _url(f"my/ships/:ship_name/dock")
        self.log_event("ship_dock", ship.name, url, response)
        pass

    def ship_refuel(self, ship: "Ship", response=None) -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/refuel"""
        url = _url(f"my/ships/:ship_name/refuel")
        self.log_event("ship_refuel", ship.name, url, response)
        pass

    def ship_sell(
        self, ship: "Ship", symbol: str, quantity: int, response=None
    ) -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/sell"""

        url = _url(f"my/ships/:ship_name/sell")
        self.log_event("ship_sell", ship.name, url, response)

        pass

    def ship_survey(
        self, ship: "ship", response=None
    ) -> list[Survey] or SpaceTradersResponse:
        """/my/ships/{shipSymbol}/survey"""
        url = _url(f"my/ships/:ship_name/survey")
        self.log_event("ship_survey", ship.name, url, response)
        pass

    def ship_transfer_cargo(
        self, ship: "Ship", trade_symbol, units, target_ship_name, response=None
    ) -> SpaceTradersResponse:
        url = _url(f"my/ships/:ship_name/transfer")
        self.log_event("ship_transfer_cargo", ship.name, url, response)

        """/my/ships/{shipSymbol}/transfer"""

        pass

    def system_market(
        self, wp: Waypoint, response=None
    ) -> Market or SpaceTradersResponse:
        """/game/systems/{symbol}/marketplace"""
        url = _url(f"game/systems/{wp.system}/marketplace")
        self.log_event("system_market", "GLOBAL", url, response)
        pass

    def systems_list_all(
        self, response=None
    ) -> dict[str:"System"] or SpaceTradersResponse:
        """/game/systems"""
        url = _url(f"game/systems")
        self.log_event("systems_list_all", "GLOBAL", url, response)
        pass

    def system_shipyard(
        self, waypoint: Waypoint, response=None
    ) -> Shipyard or SpaceTradersResponse:
        """/game/locations/{symbol}/shipyard"""
        url = _url(f"game/locations/{waypoint.symbol}/shipyard")
        self.log_event("system_shipyard", "GLOBAL", url, response)

        pass

    def ship_negotiate(
        self, ship: "ship", response=None
    ) -> "Contract" or SpaceTradersResponse:
        """/my/ships/{shipSymbol}/negotiate/contract"""
        url = _url(f"my/ships/:ship_name/negotiate/contract")

        self.log_event("ship_negotiate", ship.name, url, response)
        pass

    def ship_cooldown(self, ship: "ship", response=None) -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/cooldown"""
        url = _url(f"my/ships/:ship_name/cooldown")
        self.log_event("ship_cooldown", ship.name, url, response)
        pass

    def ships_view(self, response=None) -> list["Ship"] or SpaceTradersResponse:
        """/my/ships"""
        url = _url(f"my/ships")
        self.log_event("ships_view", "GLOBAL", url, response)

        pass

    def ships_view_one(
        self, ship_symbol: str, response=None
    ) -> "Ship" or SpaceTradersResponse:
        url = _url(f"my/ships/:ship_name")
        self.log_event("ships_view_one", ship_symbol, url, response)
        pass

    def contracts_deliver(
        self,
        contract: "Contract",
        ship: "Ship",
        trade_symbol: str,
        units: int,
        response=None,
    ) -> SpaceTradersResponse:
        url = _url(f"my/ships/:ship_name/deliver")
        self.log_event("contracts_deliver", ship.name, url, response)
        pass

    def contracts_fulfill(
        self, contract: "Contract", response=None
    ) -> SpaceTradersResponse:
        url = _url(f"my/contracts/:contract_id/fulfill")
        self.log_event("contracts_fulfill", "GLOBAL", url, response)
        pass


def _url(endpoint: str) -> str:
    # purely exists to make copy/pasting between the api client and this file faster.
    return endpoint
