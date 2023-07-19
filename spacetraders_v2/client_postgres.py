from typing import Protocol
from .models import (
    Waypoint,
    WaypointTrait,
    Market,
    Survey,
    Shipyard,
    MarketTradeGood,
    MarketTradeGoodListing,
)
from .responses import SpaceTradersResponse
from .client_interface import SpaceTradersClient
from .pg_upserts.upsert_waypoint import _upsert_waypoint
from .pg_upserts.upsert_shipyard import _upsert_shipyard
from .pg_upserts.upsert_market import _upsert_market
from .local_response import LocalSpaceTradersRespose
import psycopg2


class SpaceTradersPostgresClient(SpaceTradersClient):
    token: str = None

    def __init__(self, db_host, db_name, db_user, db_pass) -> None:
        if not db_host or not db_name or not db_user or not db_pass:
            raise ValueError("Missing database connection information")
        self.connection = psycopg2.connect(
            host=db_host, database=db_name, user=db_user, password=db_pass
        )
        self.connection.autocommit = True

    def _headers(self) -> dict:
        return {}

    def update(self, update_obj):
        if isinstance(update_obj, Waypoint):
            _upsert_waypoint(self.connection, update_obj)
        if isinstance(update_obj, Shipyard):
            _upsert_shipyard(self.connection, update_obj)
        if isinstance(update_obj, Market):
            _upsert_market(self.connection, update_obj)
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
            `system_symbol` (str): The symbol of the system to search for the waypoint in.
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
        return (
            waypoints[0]
            if len(waypoints) > 0
            else LocalSpaceTradersRespose(
                "Could not find waypoint with that symbol in DB", 0, 0, sql
            )
        )

    def find_waypoint_by_coords(
        self, system_symbol: str, x: int, y: int
    ) -> Waypoint or SpaceTradersResponse:
        pass

    def find_waypoints_by_trait(
        self, system_symbol: str, trait: str
    ) -> list[Waypoint] or SpaceTradersResponse:
        return dummy_response(__class__.__name__, __name__)

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
        return dummy_response(__class__.__name__, __name__)
        pass

    def ship_change_course(self, ship: "Ship", dest_waypoint_symbol: str):
        """my/ships/:shipSymbol/course"""
        return dummy_response(__class__.__name__, __name__)
        pass

    def ship_move(
        self, ship: "Ship", dest_waypoint_symbol: str
    ) -> SpaceTradersResponse:
        """my/ships/:shipSymbol/navigate"""

        return dummy_response(__class__.__name__, __name__)
        pass

    def ship_negotiate(self, ship: "Ship") -> "Contract" or SpaceTradersResponse:
        return dummy_response(__class__.__name__, __name__)

    def ship_extract(self, ship: "Ship", survey: Survey = None) -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/extract"""

        return dummy_response(__class__.__name__, __name__)
        pass

    def ship_dock(self, ship: "Ship") -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/dock"""
        return dummy_response(__class__.__name__, __name__)
        pass

    def ship_refuel(self, ship: "Ship") -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/refuel"""
        return dummy_response(__class__.__name__, __name__)
        pass

    def ship_sell(
        self, ship: "Ship", symbol: str, quantity: int
    ) -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/sell"""

        pass

    def ship_survey(self, ship: "Ship") -> list[Survey] or SpaceTradersResponse:
        """/my/ships/{shipSymbol}/survey"""
        return dummy_response(__class__.__name__, __name__)
        pass

    def ship_transfer_cargo(
        self, ship: "Ship", trade_symbol, units, target_ship_name
    ) -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/transfer"""
        return dummy_response(__class__.__name__, __name__)
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


def dummy_response(class_name, method_name):
    return LocalSpaceTradersRespose(
        "Not implemented in this client", 0, 0, f"{class_name}.{method_name}"
    )
