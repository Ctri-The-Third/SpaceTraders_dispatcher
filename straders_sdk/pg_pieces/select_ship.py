from ..local_response import LocalSpaceTradersRespose
from ..ship import Ship, ShipFrame, ShipNav, RouteNode
from ..client_interface import SpaceTradersClient
from ..models import ShipRequirements


def _select_ships(connection, agent_name, db_client: SpaceTradersClient):
    sql = """select s.ship_symbol, s.agent_name, s.faction_symbol, s.ship_role, s.cargo_capacity, s.cargo_in_use
                , n.waypoint_symbol, n.departure_time, n.arrival_time, n.origin_waypoint, n.destination_waypoint, n.flight_status, n.flight_mode
                , sfl.condition --13
				, sf.frame_symbol, sf.name, sf.description, sf.module_slots, sf.mount_points, sf.fuel_capacity, sf.required_power, sf.required_crew, sf.required_slots
                , s.fuel_capacity, s.fuel_current --24  
                from ship s join ship_nav n on s.ship_symbol = n.ship_symbol
				left join ship_frame_links sfl on s.ship_symbol = sfl.ship_symbol
				left join ship_frames sf on sf.frame_symbol = sfl.frame_symbol
                where s.agent_name = %s
                """
    try:
        rows = try_execute_select(connection, sql, (agent_name,))
        if not rows:
            return rows
        ships = {}
        for row in rows:
            ship = Ship()
            ship.name = row[0]
            ship.faction = row[2]
            ship.role = row[3]
            ship.cargo_capacity = row[4]
            ship.cargo_units_used = row[5]
            # , 6: n.waypoint_symbol, n.departure_time, n.arrival_time, n.origin_waypoint, n.destination_waypoint, n.flight_status, n.flight_mode
            ship.nav = _nav_from_row(row, db_client)
            ship.frame = _frame_from_row(row)
            ship.fuel_capacity = row[23]
            ship.fuel_current = row[24]
            ships[ship.name] = ship
        return ships
    except Exception as err:
        LocalSpaceTradersRespose(
            error=err,
            status_code=0,
            error_code=0,
            url=f"select_ship._select_ship",
        )
    pass


def _nav_from_row(row, db_client: SpaceTradersClient) -> ShipNav:
    # SHIP NAV BEGINS
    current_system = db_client.waypoints_view_one("", row[6])
    if not current_system:
        current_system = None

    origin = db_client.waypoints_view_one("", row[9])
    if not origin:
        origin = None
    destination = db_client.waypoints_view_one("", row[10])
    if not destination:
        destination = None

    return_obj = ShipNav(
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

    return return_obj


def _frame_from_row(row) -> ShipFrame:
    reqiurements = ShipRequirements(row[21], row[22], row[20])
    return_obj = ShipFrame(
        row[14], row[15], row[16], row[17], row[18], row[19], row[13], reqiurements
    )
    return return_obj


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
