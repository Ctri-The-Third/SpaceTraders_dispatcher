from typing import Protocol
from .models import (
    Waypoint,
    WaypointTrait,
    Market,
    Survey,
    Deposit,
    Shipyard,
    ShipyardShip,
    MarketTradeGood,
    MarketTradeGoodListing,
    System,
    Agent,
    JumpGate,
)
from .contracts import Contract
from datetime import datetime
from .responses import SpaceTradersResponse
from .client_interface import SpaceTradersClient
from .pg_pieces.upsert_waypoint import _upsert_waypoint
from .pg_pieces.upsert_shipyard import _upsert_shipyard
from .pg_pieces.upsert_market import _upsert_market
from .pg_pieces.upsert_ship import _upsert_ship
from .pg_pieces.upsert_system import _upsert_system
from .pg_pieces.upsert_survey import _upsert_survey
from .pg_pieces.select_ship import _select_ships
from .pg_pieces.jump_gates import _upsert_jump_gate, select_jump_gate_one
from .pg_pieces.agents import _upsert_agent, select_agent_one
from .pg_pieces.contracts import _upsert_contract
from .local_response import LocalSpaceTradersRespose
from .ship import Ship, ShipInventory, ShipNav, RouteNode
import psycopg2


class SpaceTradersPostgresClient(SpaceTradersClient):
    token: str = None
    current_agent_symbol: str = None

    def __init__(
        self,
        db_host,
        db_name,
        db_user,
        db_pass,
        current_agent_symbol,
        db_port=None,
    ) -> None:
        if not db_host or not db_name or not db_user or not db_pass:
            raise ValueError("Missing database connection information")
        self.connection = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_pass,
        )
        self.current_agent_symbol = current_agent_symbol
        self.connection.autocommit = True

    def _headers(self) -> dict:
        return {}

    def update(self, update_obj):
        "Accepts objects and stores them in the DB"
        if isinstance(update_obj, JumpGate):
            _upsert_jump_gate(self.connection, update_obj)
        if isinstance(update_obj, Survey):
            _upsert_survey(self.connection, update_obj)
        if isinstance(update_obj, Waypoint):
            _upsert_waypoint(self.connection, update_obj)
        if isinstance(update_obj, Shipyard):
            _upsert_shipyard(self.connection, update_obj)
        if isinstance(update_obj, Market):
            _upsert_market(self.connection, update_obj)
        if isinstance(update_obj, Ship):
            _upsert_ship(self.connection, update_obj)
        if isinstance(update_obj, System):
            _upsert_system(self.connection, update_obj)
        if isinstance(update_obj, Agent):
            _upsert_agent(self.connection, update_obj)
        if isinstance(update_obj, Contract):
            _upsert_contract(self.connection, self.current_agent_symbol, update_obj)
        pass

    def register(self, callsign, faction="COSMIC", email=None) -> SpaceTradersResponse:
        return dummy_response(__class__.__name__, "register")

    def agents_view_one(self, agent_symbol: str) -> Agent or SpaceTradersResponse:
        return select_agent_one(self.connection, agent_symbol)

    def view_my_self(self) -> Agent or SpaceTradersResponse:
        return select_agent_one(self.connection, self.current_agent_symbol)

    def view_my_contracts(self) -> list["Contract"] or SpaceTradersResponse:
        return LocalSpaceTradersRespose(
            "not implemented yet", 0, 0, f"{__name__}.view_my_contracts"
        )

    def waypoints_view(
        self, system_symbol: str
    ) -> dict[str:Waypoint] or SpaceTradersResponse:
        """view all waypoints in a system. Uses cached values by default.

        Args:
            `system_symbol` (str): The symbol of the system to search for the waypoints in.

        Returns:
            Either a dict of Waypoint objects or a SpaceTradersResponse object on failure.
        """

        sql = """SELECT * FROM waypoints WHERE system_symbol = %s"""
        cur = self.connection.cursor()
        cur.execute(sql, (system_symbol,))
        rows = cur.fetchall()
        waypoints = {}

        for row in rows:
            waypoint_symbol = row[0]
            new_sql = """SELECT * FROM waypoint_traits WHERE waypoint = %s"""
            cur.execute(new_sql, (waypoint_symbol,))
            trait_rows = cur.fetchall()
            traits = []
            for trait_row in trait_rows:
                traits.append(WaypointTrait(trait_row[1], trait_row[2], trait_row[3]))
            waypoint = Waypoint(
                row[2], row[0], row[1], row[3], row[4], [], traits, {}, {}
            )
            waypoints[waypoint.symbol] = waypoint
        return waypoints

    def waypoints_view_one(
        self, system_symbol, waypoint_symbol, force=False
    ) -> Waypoint or SpaceTradersResponse:
        """view a single waypoint in a system.

        Args:
            `system_symbol` (str): The symbol of the system to search for the waypoint in. Has no impact in this client.
            `waypoint_symbol` (str): The symbol of the waypoint to search for.
            `force` (bool): Optional - Force a refresh of the waypoint. Defaults to False.

        Returns:
            Either a Waypoint object or a SpaceTradersResponse object on failure."""
        sql = """SELECT * FROM waypoints WHERE symbol = %s LIMIT 1;"""
        cur = self.connection.cursor()
        cur.execute(sql, (waypoint_symbol,))
        rows = cur.fetchall()
        waypoints = []

        for row in rows:
            waypoint_symbol = row[0]
            new_sql = """SELECT * FROM waypoint_traits WHERE waypoint = %s"""
            cur.execute(new_sql, (waypoint_symbol,))
            trait_rows = cur.fetchall()
            traits = []
            for trait_row in trait_rows:
                traits.append(WaypointTrait(trait_row[1], trait_row[2], trait_row[3]))
            waypoint = Waypoint(
                row[2], row[0], row[1], row[3], row[4], [], traits, {}, {}
            )
            waypoints.append(waypoint)

        if len(waypoints) > 0:
            waypoints[0]: Waypoint
            return waypoints[0]
        else:
            return LocalSpaceTradersRespose(
                "Could not find waypoint with that symbol in DB", 0, 0, sql
            )

    def find_waypoint_by_coords(
        self, system_symbol: str, x: int, y: int
    ) -> Waypoint or SpaceTradersResponse:
        pass

    def find_waypoints_by_trait(
        self, system_symbol: str, trait: str
    ) -> list[Waypoint] or SpaceTradersResponse:
        return dummy_response(__class__.__name__, "find_waypoints_by_trait")

    def find_waypoints_by_trait_one(
        self, system_symbol: str, trait: str
    ) -> Waypoint or SpaceTradersResponse:
        pass

    def find_waypoints_by_type_one(
        self, system_wp: str, waypoint_type
    ) -> Waypoint or SpaceTradersResponse:
        db_wayps = self.waypoints_view(system_wp)
        if not db_wayps:
            return db_wayps
        try:
            return [wayp for wayp in db_wayps.values() if wayp.type == waypoint_type][0]
        except IndexError:
            pass
        return LocalSpaceTradersRespose(
            f"Couldn't find waypoint of type {waypoint_type} in system {system_wp}",
            0,
            0,
            f"find_waypoint_by_type({system_wp}, {waypoint_type})",
        )

    def find_survey_best_deposit(
        self, waypoint_symbol: str, deposit_symbol: str
    ) -> Survey or SpaceTradersResponse:
        sql = """select s.signature, s.waypoint, s.expiration, s.size 
                from survey_chance_and_values scv 
                join survey s on scv.signature = s.signature 
                where symbol = %s and waypoint = %s
                limit 1 
                """

        deposits_sql = (
            """select symbol, count from survey_deposit where signature = %s """
        )
        resp = try_execute_select(
            self.connection, sql, (deposit_symbol, (waypoint_symbol))
        )
        if not resp:
            if isinstance(resp, list):
                return LocalSpaceTradersRespose(
                    "Didn't find a matching survey", 0, 0, sql
                )
            return resp
        surveys = []
        for survey_row in resp:
            deposits_resp = try_execute_select(
                self.connection, deposits_sql, (survey_row[0],)
            )
            if not deposits_resp:
                return deposits_resp
            deposits = []
            deposits_json = []
            for deposit_row in deposits_resp:
                deposit = Deposit(deposit_row[0])
                for i in range(deposit_row[1]):
                    deposits.append(deposit)
                    deposits_json.append({"symbol": deposit.symbol})
            json = {
                "signature": survey_row[0],
                "symbol": survey_row[1],
                "deposits": deposits_json,
                "expiration": survey_row[2].isoformat(),
                "size": survey_row[3],
            }
            surveys.append(
                Survey(
                    survey_row[0],
                    survey_row[1],
                    deposits,
                    survey_row[2],
                    survey_row[3],
                    json,
                )
            )
        return surveys[0]

    def find_survey_best(self, waypoint_symbol: str):
        sql = """SELECT s.signature, s.waypoint, s.expiration, s.size 
                FROM survey_chance_and_values scv 
                JOIN survey s on scv.signature = s.signature 
                WHERE waypoint = %s
                LIMIT 1 
                """

        deposits_sql = (
            """select symbol, count from survey_deposit where signature = %s """
        )
        resp = try_execute_select(self.connection, sql, (waypoint_symbol,))
        if not resp:
            if isinstance(resp, list):
                return LocalSpaceTradersRespose(
                    "Didn't find a matching survey", 0, 0, sql
                )
            return resp
        surveys = []
        for survey_row in resp:
            deposits_resp = try_execute_select(
                self.connection, deposits_sql, (survey_row[0],)
            )
            if not deposits_resp:
                return deposits_resp
            deposits = []
            deposits_json = []
            for deposit_row in deposits_resp:
                deposit = Deposit(deposit_row[0])
                for i in range(deposit_row[1]):
                    deposits.append(deposit)
                    deposits_json.append({"symbol": deposit.symbol})
            json = {
                "signature": survey_row[0],
                "symbol": survey_row[1],
                "deposits": deposits_json,
                "expiration": survey_row[2].isoformat(),
                "size": survey_row[3],
            }
            surveys.append(
                Survey(
                    survey_row[0],
                    survey_row[1],
                    deposits,
                    survey_row[2],
                    survey_row[3],
                    json,
                )
            )
        return surveys[0]

    def surveys_remove_one(self, survey_signature) -> None:
        """Removes a survey from any caching - called after an invalid survey response."""
        sql = """update survey where signature = %s
        set expiration = (now() at time zone utc)"""
        resp = try_execute_no_results(self.connection, sql, (survey_signature,))
        return resp

    def ship_orbit(self, ship: "Ship") -> SpaceTradersResponse:
        """my/ships/:miningShipSymbol/orbit takes the ship name or the ship object"""
        return dummy_response(__class__.__name__, "ship_orbit")
        pass

    def ship_patch_nav(self, ship: "Ship", dest_waypoint_symbol: str):
        """my/ships/:shipSymbol/course"""
        return dummy_response(__class__.__name__, "ship_patch_nav")
        pass

    def ship_move(
        self, ship: "Ship", dest_waypoint_symbol: str
    ) -> SpaceTradersResponse:
        """my/ships/:shipSymbol/navigate"""

        return dummy_response(__class__.__name__, "ship_move")
        pass

    def ship_jump(
        self, ship: "Ship", dest_waypoint_symbol: str
    ) -> SpaceTradersResponse:
        """my/ships/:shipSymbol/jump"""
        return dummy_response(__class__.__name__, "ship_jump")
        pass

    def ship_negotiate(self, ship: "Ship") -> "Contract" or SpaceTradersResponse:
        return dummy_response(__class__.__name__, "ship_negotiate")

    def ship_extract(self, ship: "Ship", survey: Survey = None) -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/extract"""

        return dummy_response(__class__.__name__, "ship_extract")
        pass

    def ship_dock(self, ship: "Ship") -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/dock"""
        return dummy_response(__class__.__name__, "ship_dock")
        pass

    def ship_refuel(self, ship: "Ship") -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/refuel"""
        return dummy_response(__class__.__name__, "ship_refuel")
        pass

    def ship_sell(
        self, ship: "Ship", symbol: str, quantity: int
    ) -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/sell"""

        pass

    def ship_survey(self, ship: "Ship") -> list[Survey] or SpaceTradersResponse:
        """/my/ships/{shipSymbol}/survey"""
        return dummy_response(__class__.__name__, "ship_survey")
        pass

    def ship_transfer_cargo(
        self, ship: "Ship", trade_symbol, units, target_ship_name
    ) -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/transfer"""
        return dummy_response(__class__.__name__, "ship_transfer_cargo")
        pass

    def system_market(self, wp: Waypoint) -> Market or SpaceTradersResponse:
        """/game/systems/{symbol}/marketplace"""
        try:
            sql = """SELECT mt.symbol, mt.name, mt.description FROM market_tradegood mt where mt.market_waypoint =  %s"""
            cur = self.connection.cursor()
            cur.execute(sql, (wp.symbol,))
            rows = cur.fetchall()
            if not rows:
                return LocalSpaceTradersRespose(
                    f"Could not find market data for that waypoint", 0, 0, sql
                )
            imports = [MarketTradeGood(*row) for row in rows if row[2] == "buy"]
            exports = [MarketTradeGood(*row) for row in rows if row[2] == "sell"]
            return Market(wp.symbol, imports, exports, [])
        except Exception as err:
            return LocalSpaceTradersRespose(
                "Could not find market data for that waypoint", 0, 0, sql
            )

    def system_jumpgate(self, wp: Waypoint) -> JumpGate or SpaceTradersResponse:
        return select_jump_gate_one(self.connection, wp)

    def systems_view_all(self) -> list["Waypoint"] or SpaceTradersResponse:
        """/game/systems"""
        sql = """SELECT symbol, sector_symbol, type, x, y FROM systems"""
        cur = self.connection.cursor()
        cysts = {}
        try:
            cur.execute(sql)
            rows = cur.fetchall()
        except Exception as err:
            return LocalSpaceTradersRespose(
                f"Wasn't able to get waypoints {err}",
                0,
                0,
                __name__ + ".systems_list_all",
            )
        for row in rows:
            syst = System(row[0], row[1], row[2], row[3], row[4], [])
            cysts[syst.symbol] = syst
        return cysts

    def systems_view_one(self, symbol: str) -> Waypoint or SpaceTradersResponse:
        sql = """SELECT symbol, sector_symbol, type, x, y FROM systems where symbol = %s limit 1"""
        cur = self.connection.cursor()
        try:
            cur.execute(sql, (symbol,))
            rows = cur.fetchall()
        except Exception as err:
            return LocalSpaceTradersRespose(
                f"Wasn't able to get waypoint {err}",
                0,
                0,
                __name__ + ".systems_list_all",
            )
        for row in rows:
            syst = System(row[0], row[1], row[2], row[3], row[4], [])
            return syst

    def system_shipyard(self, wp: Waypoint) -> Shipyard or SpaceTradersResponse:
        """View the types of ships available at a shipyard.

        Args:
            `wp` (Waypoint): The waypoint to view the ships at.

        Returns:
            Either a list of ship types (symbols for purchase) or a SpaceTradersResponse object on failure.
        """
        sql = """SELECT ship_type, ship_cost  FROM shipyard_types where shipyard_symbol = %s"""
        try:
            cu = self.connection.cursor()
            cu.execute(sql, (wp.symbol,))
            rows = cu.fetchall()
            if len(rows) >= 1:
                types = [row[0] for row in rows]
                ships = {
                    row[0]: ShipyardShip(
                        None, None, None, row[0], None, row[0], row[1], [], []
                    )
                    for row in rows
                }
                found_shipyard = Shipyard(wp.symbol, types, ships)
                return found_shipyard
        except Exception as err:
            return LocalSpaceTradersRespose(
                error=f"Did not find shipyard at that waypoint, {err}",
                status_code=0,
                error_code=0,
                url=f"{__class__.__name__}.system_shipyard({wp.symbol}",
            )

    def ship_cooldown(self, ship: "Ship") -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/cooldown"""
        dummy_response(__class__.__name__, "ship_cooldown")

    def ships_purchase(
        self, ship_type: str, shipyard_waypoint: str
    ) -> tuple["Ship", "Agent"] or SpaceTradersResponse:
        dummy_response(__class__.__name__, "ships_purchase")

    def ships_view(self) -> dict[str:"Ship"] or SpaceTradersResponse:
        """/my/ships"""

        # PROBLEM - the client doesn't really know who the current agent is - so we can't filter by agent.
        # but the DB is home to many ships. Therefore, this client needs to become aware of the agent name on init.
        # WAIT WE ALREADY DO THAT. well done past C'tri

        return _select_ships(self.connection, self.current_agent_symbol, self)

    def ships_view_one(self, symbol: str) -> "Ship" or SpaceTradersResponse:
        """/my/ships/{shipSymbol}"""
        ships = self.ships_view()
        ship = ships.get(
            symbol,
            LocalSpaceTradersRespose(
                "Ship not found in DB", 0, 404, "client_postgres.ships_view_one"
            ),
        )
        return ship

    def contracts_deliver(
        self, contract: "Contract", ship: "Ship", trade_symbol: str, units: int
    ) -> SpaceTradersResponse:
        dummy_response(__class__.__name__, "contracts_deliver")
        pass

    def contracts_fulfill(self, contract: "Contract") -> SpaceTradersResponse:
        dummy_response(__class__.__name__, "contracts_fulfill")
        pass


def dummy_response(class_name, method_name):
    return LocalSpaceTradersRespose(
        "Not implemented in this client", 0, 0, f"{class_name}.{method_name}"
    )


def try_execute_select(connection, sql, params) -> list:
    try:
        cur = connection.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        return rows
    except Exception as err:
        return LocalSpaceTradersRespose(
            error=err, status_code=0, error_code=0, url=f"{__name__}.try_execute_select"
        )


def try_execute_no_results(connection, sql, params) -> LocalSpaceTradersRespose:
    try:
        cur = connection.cursor()
        cur.execute(sql, params)
        connection.commit()
        return LocalSpaceTradersRespose(
            error=None, status_code=0, error_code=0, url=f"{__name__}.try_execute"
        )
    except Exception as err:
        return LocalSpaceTradersRespose(
            error=err, status_code=0, error_code=0, url=f"{__name__}.try_execute"
        )
