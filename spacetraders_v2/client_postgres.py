from typing import Protocol
from .models import Waypoint, WaypointTrait, Market, Survey
from .responses import SpaceTradersResponse
from .client_interface import SpaceTradersClient
from .local_response import LocalSpaceTradersRespose
import psycopg2


class SpaceTradersPostgresClient(SpaceTradersClient):
    token: str = None

    def __init__(self,, db_host, db_name, db_user, db_pass) -> None:
        
        if not db_host or not db_name or not db_user or not db_pass:
            raise ValueError("Missing database connection information")
        self.connection = psycopg2.connect(
            host=db_host, database=db_name, user=db_user, password=db_pass
        )

    def _headers(self) -> dict:
        return {}

    def update(self, update_obj):
        if isinstance(update_obj, Waypoint):
            self._upsert_waypoint(update_obj)
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
        pass

    def find_waypoints_by_trait_one(
        self, system_symbol: str, trait: str
    ) -> Waypoint or SpaceTradersResponse:
        pass

    def find_waypoint_by_type(
        self, system_wp, waypoint_type
    ) -> Waypoint or SpaceTradersResponse:
        db_wayps = self.waypoints_view(system_wp.symbol)
        return [wayp for wayp in db_wayps.values() if wayp.type == waypoint_type][0]

    def ship_orbit(self, ship: "Ship") -> SpaceTradersResponse:
        """my/ships/:miningShipSymbol/orbit takes the ship name or the ship object"""
        pass

    def ship_change_course(self, ship: "Ship", dest_waypoint_symbol: str):
        """my/ships/:shipSymbol/course"""
        pass

    def ship_move(
        self, ship: "Ship", dest_waypoint_symbol: str
    ) -> SpaceTradersResponse:
        """my/ships/:shipSymbol/navigate"""

        pass

    def ship_extract(self, ship: "Ship", survey: Survey = None) -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/extract"""

        pass

    def ship_dock(self, ship: "Ship") -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/dock"""
        pass

    def ship_refuel(self, ship: "Ship") -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/refuel"""
        pass

    def ship_sell(
        self, ship: "Ship", symbol: str, quantity: int
    ) -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/sell"""

        pass

    def ship_survey(self, ship: "Ship") -> list[Survey] or SpaceTradersResponse:
        """/my/ships/{shipSymbol}/survey"""

        pass

    def ship_transfer_cargo(
        self, ship: "Ship", trade_symbol, units, target_ship_name
    ) -> SpaceTradersResponse:
        """/my/ships/{shipSymbol}/transfer"""

        pass

    def system_market_view(
        self, system_symbol: str, waypoint_symbol: str
    ) -> Market or SpaceTradersResponse:
        """/game/systems/{symbol}/marketplace"""

        pass

    def _upsert_waypoint(self, waypoint: Waypoint):
        try:
            sql = """INSERT INTO waypoints (symbol, type, system_symbol, x, y)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (symbol) DO UPDATE
                        SET type = %s,  system_symbol = %s, x = %s, y = %s"""
            self.connection.cursor().execute(
                sql,
                (
                    waypoint.symbol,
                    waypoint.type,
                    waypoint.system_symbol,
                    waypoint.x,
                    waypoint.y,
                    waypoint.type,
                    waypoint.system_symbol,
                    waypoint.x,
                    waypoint.y,
                ),
            )

            for trait in waypoint.traits:
                sql = """INSERT INTO waypoint_traits (waypoint, symbol, name, description)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (waypoint, symbol) DO UPDATE
                            SET name = %s, description = %s"""
                self.connection.cursor().execute(
                    sql,
                    (
                        waypoint.symbol,
                        trait.symbol,
                        trait.name,
                        trait.description,
                        trait.name,
                        trait.description,
                    ),
                )
            self.connection.commit()
        except Exception as err:
            print(err)
            self.connection.rollback()
