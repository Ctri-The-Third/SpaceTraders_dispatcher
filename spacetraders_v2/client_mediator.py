from .utils import get_and_validate, get_and_validate_paginated, post_and_validate, _url
from .utils import ApiConfig, _log_response
from .client_interface import SpaceTradersInteractive, SpaceTradersClient

from .responses import SpaceTradersResponse
from .local_response import LocalSpaceTradersRespose
from .contracts import Contract
from .models import Waypoint, ShipyardShip, GameStatus, Agent, Survey, Nav, Market
from .models import Shipyard
from .ship import Ship
from .client_api import SpaceTradersApiClient
from .client_postgres import SpaceTradersPostgresClient
from threading import Lock
import logging

# Attempted relative import beyond top-level packagePylintE0402:relative-beyond-top-level
from datetime import datetime


class SpaceTradersMediatorClient(SpaceTradersClient):
    """SpaceTraders API client, with in-memory caching, and DB lookup."""

    api_client: SpaceTradersClient
    db_client: SpaceTradersClient
    current_agent: Agent
    ships: dict[str, Ship]
    waypoints: dict[str, Waypoint]
    system_waypoints: dict[str : list[Waypoint]]

    def __init__(
        self,
        token=None,
        base_url=None,
        version=None,
        db_host=None,
        db_name=None,
        db_user=None,
        db_pass=None,
    ) -> None:
        self.token = token
        self.db_client = SpaceTradersPostgresClient(
            db_host=db_host, db_name=db_name, db_user=db_user, db_pass=db_pass
        )
        self.api_client = SpaceTradersApiClient(
            token=token, base_url=base_url, version=version
        )
        self.config = ApiConfig(
            base_url=base_url, version=version
        )  # set up the global config for other things to use.
        self.ships = {}
        self.waypoints = {}
        self.contracts = {}
        self.system_waypoints = {}
        self.current_agent = None
        self.surveys: dict[str:Survey] = {}
        self._lock = Lock()
        self.logger = logging.getLogger(__name__)

    def game_status(self) -> GameStatus:
        """Get the status of the SpaceTraders game server.

        Args:
            None"""

        url = _url("")
        resp = get_and_validate(url)

        return GameStatus(resp.response_json)

    def register(self, callsign, faction="COSMIC", email=None) -> SpaceTradersResponse:
        """Register a new agent.

        Args:
            `callsign` (str): The callsign of the agent
            `faction` (str): The faction the agent will be a part of. Defaults to "COSMIC"
            `email` (str): The email of the agent. Optional. Used for managing tokens in the SpaceTraders UI.
        """
        url = _url("register")
        data = {"symbol": callsign, "faction": faction}
        if email is not None:
            data["email"] = email
        resp = post_and_validate(url, data)
        if resp:
            self.token = resp.data.get("token")
        return resp

    def view_my_self(self, force=False) -> Agent or None:
        """view the current agent, uses cached value unless forced.

        Args:
            `force` (bool): Optional - Force a refresh of the agent. Defaults to False.
        """
        if self.current_agent and not force:
            return self.current_agent
        url = _url("my/agent")
        resp = get_and_validate(url, headers=self._headers())
        if resp:
            self.current_agent = Agent.from_json(resp.data)
        return self.current_agent

    def ships_view(self, force=False) -> dict[str, Ship] or SpaceTradersResponse:
        """view the current ships the agent has, a dict that's accessible by ship symbol.
        uses cached values by default.

        Args:
            `force` (bool): Optional - Force a refresh of the ships. Defaults to False.
        """
        if not force and len(self.ships) > 0:
            return self.ships

        if not force:
            resp = self.db_client.ships_view()
            if resp:
                self.ships = self.ships | resp
                return resp

        resp = self.api_client.ships_view()
        if resp:
            new_ships = {ship["symbol"]: Ship(ship, self) for ship in resp.data}
            self.ships = self.ships | new_ships
            for ship in self.ships:
                self.db_client.update(ship)
            return new_ships
        return resp

    def ships_view_one(self, symbol: str, force=False):
        if not force and symbol in self.ships:
            resp = self.ships.get(symbol, None)
            if resp:
                return self.ships[symbol]

        if not force:
            resp = self.db_client.ships_view_one(symbol)
            if resp:
                resp: Ship
                self.ships[symbol] = resp
                return resp

        resp = self.api_client.ships_view_one(symbol)
        if resp:
            resp: Ship
            self.ships[symbol] = resp
            self.db_client.update(resp)
        return resp

    def ship_purchase(
        self, waypoint: str or Waypoint, ship_type: str or ShipyardShip
    ) -> Ship or SpaceTradersResponse:
        """purchase a ship from a given shipyard waypoint.

        Args:
            `waypoint` (str or Waypoint): The waypoint to purchase the ship from. Can be a waypoint symbol or a Waypoint object.
            `ship_type` (str or ShipyardShip): The type of ship to purchase. Can be a ship_type identifier or a ShipyardShip object.

            Returns:
                Either a Ship object or a SpaceTradersResponse object on failure."""
        ship_type = ship_type.type if isinstance(ship_type, ShipyardShip) else ship_type
        waypoint = waypoint.symbol if isinstance(waypoint, Waypoint) else waypoint

        url = _url("my/ships")
        data = {"shipType": ship_type, "waypointSymbol": waypoint}
        resp = post_and_validate(url, data, headers=self._headers())
        if not resp:
            return resp
        new_ship = Ship(resp.data["ship"], self)
        self.ships[new_ship.name] = new_ship
        return new_ship

    def view_my_contracts(
        self, force=False
    ) -> dict[str, Contract] or SpaceTradersResponse:
        """view the current contracts the agent has, uses cached values by default.

        Args:
            `force` (bool): Optional - Force a refresh of the contracts. Defaults to False.

        Returns:
            Either a dict of Contract objects or a SpaceTradersResponse object on failure.
        """
        if self.contracts and not force:
            return self.contracts
        url = _url("my/contracts")
        resp = get_and_validate(url, headers=self._headers())  #
        if not resp:
            return resp

        self.contracts = self.contracts | {
            c["id"]: Contract(c, self) for c in resp.data
        }
        for contract in self.contracts.values():
            contract.client = self
        return self.contracts

    def contract_accept(self, contract_id) -> Contract or SpaceTradersResponse:
        """accept a contract

        Args:
            `contract_id` (str): The id of the contract to accept.

        Returns:
                Either a Contract object or a SpaceTradersResponse object on failure."""
        url = _url(f"my/contracts/{contract_id}/accept")
        resp = post_and_validate(url, headers=self._headers())

        if not resp:
            return resp
        new_contract = Contract(resp.data["contract"], self)
        self.contracts[new_contract.id] = new_contract
        return new_contract

    def update(self, json_data):
        """Parses the json data from a response to update the agent, add a new survey, or add/update a new contract.

        This method is present on all Classes that can cache responses from the API."""
        if isinstance(json_data, SpaceTradersResponse):
            if json_data.data is not None:
                json_data = json_data.data
        if isinstance(json_data, dict):
            if "agent" in json_data:
                self.current_agent.update(json_data)
            if "surveys" in json_data:
                for survey in json_data["surveys"]:
                    self.surveys[survey["signature"]] = Survey.from_json(survey)
            if "contract" in json_data:
                self.contracts[json_data["contract"]["id"]] = Contract(
                    json_data["contract"], self
                )
            if "nav" in json_data:
                pass  # this belongs to a ship, can't exist by itself. Call ship.update(json_data) instead
            if "cooldown" in json_data:
                pass  # this belongs to a ship, can't exist by itself. Call ship.update(json_data) instead
        if isinstance(json_data, Survey):
            self.surveys[json_data.signature] = json_data
        if isinstance(json_data, list):
            for contract in json_data:
                self.contracts[contract["id"]] = Contract(contract, self)

        if isinstance(json_data, Waypoint):
            self.waypoints[json_data.symbol] = json_data

    def waypoints_view_one(
        self, system_symbol, waypoint_symbol, force=False
    ) -> Waypoint or SpaceTradersResponse:
        # check self
        if waypoint_symbol in self.waypoints and not force:
            return self.waypoints[waypoint_symbol]

        # check db
        wayp = self.db_client.waypoints_view_one(system_symbol, waypoint_symbol)
        if wayp:
            self.update(wayp)
            return wayp
        # check api
        wayp = self.api_client.waypoints_view_one(system_symbol, waypoint_symbol)
        if wayp:
            self.update(wayp)
            self.db_client.update(wayp)
            return wayp
        return wayp

    def waypoints_view(
        self, system_symbol: str
    ) -> dict[str:Waypoint] or SpaceTradersResponse:
        """view all waypoints in a system. Uses cached values by default.

        Args:
            `system_symbol` (str): The symbol of the system to search for the waypoints in.

        Returns:
            Either a dict of Waypoint objects or a SpaceTradersResponse object on failure.
        """
        # check cache
        if system_symbol in self.system_waypoints:
            return self.system_waypoints[system_symbol]

        new_wayps = self.db_client.waypoints_view(system_symbol)
        if new_wayps:
            for new_wayp in new_wayps.values():
                self.update(new_wayp)
            return new_wayps

        new_wayps = self.api_client.waypoints_view(system_symbol)
        if new_wayps:
            for new_wayp in new_wayps.values():
                self.db_client.update(new_wayp)
                self.update(new_wayp)
        return new_wayps

    def view_my_ships_one(
        self, ship_id: str, force=False
    ) -> Ship or SpaceTradersResponse:
        """view a single ship owned by the agent. Uses cached values by default.


        Args:
            `ship_id` (str): The id of the ship to view.
            `force` (bool): Optional - Force a refresh of the ship. Defaults to False.

        Returns:
            Either a Ship object or a SpaceTradersResponse object on failure."""

        if ship_id in self.ships and not force:
            return self.ships[ship_id]
        url = _url(f"my/ships/{ship_id}")
        resp = get_and_validate(url, headers=self._headers())
        if not resp:
            return resp
        ship = Ship(resp.data, self)
        self.ships[ship_id] = ship
        return ship

    def system_shipyard(
        self, wp: Waypoint, force_update=False
    ) -> Shipyard or SpaceTradersResponse:
        """View the types of ships available at a shipyard.

        Args:
            `wp` (Waypoint): The waypoint to view the ships at.

        Returns:
            Either a list of ship types (symbols for purchase) or a SpaceTradersResponse object on failure.
        """
        if not force_update:
            resp = self.db_client.system_shipyard(wp)
            if bool(resp):
                return resp

        resp = self.api_client.system_shipyard(wp)
        if resp:
            self.db_client.update(resp)
        return resp

    def system_market(
        self, wp: Waypoint, force_update=False
    ) -> Market or SpaceTradersResponse:
        if not force_update:
            resp = self.db_client.system_market(wp)
            if bool(resp):
                return resp
        resp = self.api_client.system_market(wp)
        if bool(resp):
            self.db_client.update(resp)
            return resp
        return resp

    def view_available_ships_details(
        self, wp: Waypoint
    ) -> dict[str:ShipyardShip] or SpaceTradersResponse:
        """view the available ships at a shipyard. Note, requires a vessel to be at the waypoint to provide details

        Args:
            `wp` (Waypoint): The waypoint to view the ships at.

        Returns:
            Either a dict of ShipyardShip objects or a SpaceTradersResponse object on failure.
        """

        url = _url(f"systems/{wp.system_symbol}/waypoints/{wp.symbol}/shipyard")
        resp = get_and_validate(url, headers=self._headers())
        if resp and (resp.data is None or "ships" not in resp.data):
            return LocalSpaceTradersRespose(
                "No ship at this waypoint to get details.", 200, 0, url
            )
        if resp:
            return {d["type"]: ShipyardShip.from_json(d) for d in resp.data["ships"]}

        return resp

    def find_surveys(
        self, waypoint_symbol: str = None, material_symbol: str = None
    ) -> list[Survey]:
        """filter cached surveys by system, and material

        Args:
            `waypoint_symbol` (str): Optional - The symbol of the waypoint to filter by.
            `material_symbol` (str): Optional - The symbol of the material we're looking for.

        Returns:
            A list of Survey objects that match the filter. If no filter is provided, all surveys are returned.
        """
        matching_surveys = []
        surveys_to_remove = []
        for survey in self.surveys.values():
            survey: Survey
            if survey.expiration < datetime.utcnow():
                surveys_to_remove.append(survey.signature)
                continue
            if waypoint_symbol and survey.symbol != waypoint_symbol:
                continue
            if material_symbol:
                for deposit in survey.deposits:
                    if deposit.symbol == material_symbol:
                        matching_surveys.append(survey)
        for sig in surveys_to_remove:
            self.surveys.pop(sig)
        return matching_surveys

    def find_survey_best(
        self,
        material_symbol,
        waypoint_symbol=None,
    ) -> Survey or None:
        """find the survey with the best chance of giving a specific material.

        Args:
            `material_symbol` (str): Required - The symbol of the material we're looking for.
            `waypoint_symbol` (str): Optional - The symbol of the waypoint to filter by.

        Returns:
            A Survey object that has the best chance of giving the material. If no matching survey is found, None is returned.
        """
        surveys = self.find_surveys(waypoint_symbol, material_symbol)
        best_survey = None
        best_chance = 0
        for survey in surveys:
            deposits = len(survey.deposits)
            chance = sum(
                1 for deposit in survey.deposits if deposit.symbol == material_symbol
            )

            chance = chance / deposits
            if chance > best_chance:
                best_chance = chance
                best_survey = survey
        logging.debug("best survey: (%s%%)", best_chance)
        return best_survey

    def find_waypoint_by_coords(self, system: str, x: int, y: int) -> Waypoint or None:
        """find a waypoint by its coordinates. Only searches cached values.

        Args:
            `system` (str): The symbol of the system to search in.
            `x` (int): The x coordinate of the waypoint.
            `y` (int): The y coordinate of the waypoint.

        Returns:
            Either a Waypoint object or None if no matching waypoint is found.
        """
        for waypoint in self.waypoints.values():
            if waypoint.system_symbol == system and waypoint.x == x and waypoint.y == y:
                return waypoint
        return None

    def find_waypoint_by_type(
        self, system_wp, waypoint_type
    ) -> Waypoint or SpaceTradersResponse or None:
        """find a waypoint by its type. searches cached values first, then makes a request if no match is found.

        Args:
            `system_wp` (str): The symbol of the system to search in.
            `waypoint_type` (str): The type of waypoint to search for.

        returns:
            Either a Waypoint object or a SpaceTradersResponse object on API failure.
            If no matching waypoint is found and no errors occur, None is returned.
        """
        for waypoint in self.waypoints.values():
            if waypoint.system_symbol == system_wp and waypoint.type == waypoint_type:
                return waypoint
        resp = self.waypoints_view(system_wp)
        if not resp:
            return resp
        for waypoint in self.waypoints_view(system_wp).values():
            if waypoint.type == waypoint_type:
                return waypoint

    def find_waypoints_by_trait(
        self, system_symbol: str, trait: str
    ) -> list[Waypoint] or SpaceTradersResponse:
        resp = []
        for wayp in self.waypoints_view(system_symbol).values():
            wayp: Waypoint
            for wp_trait in wayp.traits:
                if wp_trait.symbol == trait:
                    resp.append(wayp)

        resp = [
            wayp
            for wayp in self.waypoints_view(system_symbol).values()
            for wp_trait in wayp.traits
            if wp_trait.symbol == trait
        ]
        if isinstance(resp, list) and len(resp) > 0:
            return resp
        resp = self.db_client.find_waypoints_by_trait(system_symbol, trait)
        if resp:
            return resp
        wayps = self.api_client.find_waypoints_by_trait(system_symbol, trait)
        if isinstance(wayps, list):
            wayps: list
            for wayp in wayps:
                self.db_client.update(wayp)
                self.update(wayp)
        return wayps

    def find_waypoints_by_trait_one(
        self, system_wp: str, trait_symbol: str
    ) -> Waypoint or None:
        """find a waypoint by its trait. searches cached values first, then makes a request if no match is found.
        If there are multiple matching waypoints, only the first one is returned.

        Args:
            `system_wp` (str): The symbol of the system to search in.
            `trait_symbol` (str): The symbol of the trait to search for.

        Returns:
            Either a Waypoint object or None if no matching waypoint is found."""
        for waypoint in self.waypoints.values():
            for trait in waypoint.traits:
                if waypoint.system_symbol == system_wp and trait.symbol == trait_symbol:
                    return waypoint
        resp = self.waypoints_view(system_wp)
        if not resp:
            return resp
        for waypoint in self.waypoints_view(system_wp).values():
            waypoint: Waypoint
            for trait in waypoint.traits:
                if trait.symbol == trait_symbol:
                    return waypoint

    def ship_orbit(self, ship: "Ship"):
        """my/ships/:miningShipSymbol/orbit takes the ship name or the ship object"""
        if ship.nav.status == "IN_ORBIT":
            return LocalSpaceTradersRespose(
                None, 200, "Ship is already in orbit", "client_mediator.ship_orbit()"
            )
        resp = self.api_client.ship_orbit(ship)
        if resp:
            ship.update(resp.data)
        return

    def ship_change_course(self, ship: "Ship", dest_waypoint_symbol: str):
        """my/ships/:shipSymbol/course"""
        return self.api_client.ship_change_course(ship, dest_waypoint_symbol)

    def ship_move(self, ship: "Ship", dest_waypoint_symbol: str):
        """my/ships/:shipSymbol/navigate"""
        if ship.nav.waypoint_symbol == dest_waypoint_symbol:
            return LocalSpaceTradersRespose(
                f"Navigate request failed. Ship '{ship.name}' is currently located at the destiatnion.",
                400,
                4204,
                "client_mediator.ship_move()",
            )
        resp = self.api_client.ship_move(ship, dest_waypoint_symbol)
        if resp:
            ship.update(resp.data)
            self.db_client.update(ship)
            self.ships[ship.name] = ship
        return resp

    def ship_negotiate(self, ship: "Ship") -> "Contract" or SpaceTradersResponse:
        """/my/ships/{shipSymbol}/negotiate/contract"""
        if ship.nav.status != "DOCKED":
            self.ship_dock(ship)
        resp = self.api_client.ship_negotiate(ship)
        if bool(resp):
            self.update(resp)
        return resp

    def ship_extract(self, ship: "Ship", survey: Survey = None) -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/extract"""
        # 4228 / 400 - MAXIMUM CARGO, should not extract
        #
        resp = self.api_client.ship_extract(ship, survey)
        if resp:
            ship.update(resp.data)
            self.db_client.update(ship)
        if not resp:
            self.logger.error(
                "status_code = %s, error_code = %s,  error = %s",
                resp.status_code,
                resp.error_code,
                resp.error,
            )
        return resp

    def ship_dock(self, ship: "Ship"):
        """/my/ships/{shipSymbol}/dock"""
        resp = self.api_client.ship_dock(ship)
        if resp:
            ship.update(resp.data)
            self.db_client.update(ship)
        return resp

    def ship_refuel(self, ship: "Ship"):
        """/my/ships/{shipSymbol}/refuel"""
        resp = self.api_client.ship_refuel(ship)
        if resp:
            ship.update(resp.data)
            self.db_client.update(ship)

    def ship_sell(
        self, ship: "Ship", symbol: str, quantity: int
    ) -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/sell"""
        resp = self.api_client.ship_sell(ship, symbol, quantity)
        if resp:
            ship.update(resp.data)
            self.db_client.update(resp)
            self.update(resp.data)
        return resp

    def ship_survey(self, ship: "Ship") -> list[Survey] or SpaceTradersResponse:
        """/my/ships/{shipSymbol}/survey"""
        resp = self.api_client.ship_survey(ship)
        if resp:
            surveys = [Survey.from_json(d) for d in resp.data.get("surveys", [])]
            for survey in surveys:
                self.db_client.update(survey)
            self.update(resp.data)
            ship.update(resp.data)

        elif resp.data is not None:
            self.update(resp.data)
        return resp

    def ship_transfer_cargo(self, ship: "Ship", trade_symbol, units, target_ship_name):
        """/my/ships/{shipSymbol}/transfer"""
        resp = self.api_client.ship_transfer_cargo(
            ship, trade_symbol, units, target_ship_name
        )
        if resp:
            ship.update(resp.data)
        return resp

    def ship_cooldown(self, ship: "Ship") -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/cooldown"""
        resp = self.api_client.ship_cooldown(ship)
        if resp:
            ship.update(resp.data)
        return resp

    def contracts_deliver(
        self, contract: Contract, ship: Ship, trade_symbol: str, units: int
    ) -> SpaceTradersResponse:
        resp = self.api_client.contracts_deliver(contract, ship, trade_symbol, units)
        if resp:
            self.update(resp.data)
            contract.update(resp.data)
            ship.update(resp.data)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}
