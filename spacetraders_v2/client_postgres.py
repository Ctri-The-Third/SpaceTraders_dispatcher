from typing import Protocol
from .models import (
    Waypoint,
    WaypointTrait,
    Market,
    Survey,
    Shipyard,
    MarketTradeGood,
    MarketTradeGoodListing,
    System,
)
from .responses import SpaceTradersResponse
from .client_interface import SpaceTradersClient
from .pg_upserts.upsert_waypoint import _upsert_waypoint
from .pg_upserts.upsert_shipyard import _upsert_shipyard
from .pg_upserts.upsert_market import _upsert_market
from .pg_upserts.upsert_ship import _upsert_ship
from .pg_upserts.upsert_system import _upsert_system
from .local_response import LocalSpaceTradersRespose
from .ship import Ship, ShipInventory, ShipNav, RouteNode, Ship
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
        pass

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

    def find_waypoint_by_type(
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

    def ship_orbit(self, ship: "Ship") -> SpaceTradersResponse:
        """my/ships/:miningShipSymbol/orbit takes the ship name or the ship object"""
        return dummy_response(__class__.__name__, "ship_orbit")
        pass

    def ship_change_course(self, ship: "Ship", dest_waypoint_symbol: str):
        """my/ships/:shipSymbol/course"""
        return dummy_response(__class__.__name__, "ship_change_course")
        pass

    def ship_move(
        self, ship: "Ship", dest_waypoint_symbol: str
    ) -> SpaceTradersResponse:
        """my/ships/:shipSymbol/navigate"""

        return dummy_response(__class__.__name__, "ship_move")
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
            imports = [MarketTradeGood(*row) for row in rows if row[2] == "buy"]
            exports = [MarketTradeGood(*row) for row in rows if row[2] == "sell"]
            return Market(wp.symbol, imports, exports, [])
        except Exception as err:
            return LocalSpaceTradersRespose(
                "Could not find market data for that waypoint", 0, 0, sql
            )

    def systems_list_all(self) -> list["Waypoint"] or SpaceTradersResponse:
        """/game/systems"""
        sql = """SELECT * FROM waypoints"""
        cur = self.connection.cursor()
        wayps = {}
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
            wayp = Waypoint(row[2], row[0], row[1], row[3], row[4], [], [], {}, {})
            wayps[wayp.symbol] = wayp
        return wayps

    def system_shipyard(self, wp: Waypoint) -> list[str] or SpaceTradersResponse:
        """View the types of ships available at a shipyard.

        Args:
            `wp` (Waypoint): The waypoint to view the ships at.

        Returns:
            Either a list of ship types (symbols for purchase) or a SpaceTradersResponse object on failure.
        """
        sql = """SELECT * FROM shipyard_types where shipyard_symbol = %s"""
        try:
            cu = self.connection.cursor()
            cu.execute(sql, (wp.symbol,))
            rows = cu.fetchall()
            if len(rows) >= 1:
                types = [row[1] for row in rows]
                found_shipyard = Shipyard(wp.symbol, types, {})
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
        sql = """select s.ship_symbol, s.agent_name, s.faction_symbol, s.ship_role, s.cargo_capacity, s.cargo_in_use
                , n.waypoint_symbol, n.departure_time, n.arrival_time, n.origin_waypoint, n.destination_waypoint, n.flight_status, n.flight_mode
                from ship s join ship_nav n on s.ship_symbol = n.ship_symbol
                where agent_name = %s
                
                """
        try:
            cur = self.connection.cursor()
            cur.execute(sql, (self.current_agent_symbol,))
            rows = cur.fetchall()
            ships = {}
            for row in rows:
                ship = Ship()
                ship.name = row[0]
                ship.faction = row[2]
                ship.role = row[3]
                ship.cargo_capacity = row[4]
                ship.cargo_units_used = row[5]
                # , 6: n.waypoint_symbol, n.departure_time, n.arrival_time, n.origin_waypoint, n.destination_waypoint, n.flight_status, n.flight_mode

                # SHIP NAV BEGINS
                current_system = self.waypoints_view_one("", row[6])
                if not current_system:
                    current_system = None

                origin = self.waypoints_view_one("", row[9])
                if not origin:
                    origin = None
                destination = self.waypoints_view_one("", row[10])
                if not destination:
                    destination = None

                ship.nav = ShipNav(
                    current_system.system_symbol,
                    current_system.symbol,
                    RouteNode(
                        destination.symbol,
                        destination.type,
                        destination.system_symbol,
                        destination.x,
                        destination.y,
                    ),
                    RouteNode(
                        origin.symbol,
                        origin.type,
                        origin.system_symbol,
                        origin.x,
                        origin.y,
                    ),
                    row[7],
                    row[8],
                    row[11],
                    row[12],
                )
                # SHIP NAV ENDS

                ships[ship.name] = ship
            return ships
        except Exception as err:
            LocalSpaceTradersRespose(
                error=err,
                status_code=0,
                error_code=0,
                url=f"{__class__.__name__}.ships_view",
            )
        pass

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
