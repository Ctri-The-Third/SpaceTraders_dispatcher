from ..local_response import LocalSpaceTradersRespose
from ..ship import Ship, ShipFrame, ShipNav, RouteNode
from ..client_interface import SpaceTradersClient
from ..models import ShipRequirements
from ..utils import try_execute_select, try_execute_upsert


def _select_ships(connection, agent_name, db_client: SpaceTradersClient):
    sql = """select s.ship_symbol, s.agent_name, s.faction_symbol, s.ship_role, s.cargo_capacity, s.cargo_in_use
                , n.waypoint_symbol, n.departure_time, n.arrival_time, n.o_waypoint_symbol, n.d_waypoint_symbol, n.flight_status, n.flight_mode
                , sfl.condition --13
				, sf.frame_symbol, sf.name, sf.description, sf.module_slots, sf.mount_points, sf.fuel_capacity, sf.required_power, sf.required_crew, sf.required_slots
                , s.fuel_capacity, s.fuel_current --24  
                , sc.expiration, sc.total_seconds --26
                from ships s join ship_nav n on s.ship_symbol = n.ship_symbol
				left join ship_frame_links sfl on s.ship_symbol = sfl.ship_symbol
				left join ship_frames sf on sf.frame_symbol = sfl.frame_symbol
                left join ship_cooldown sc on s.ship_symbol = sc.ship_symbol
                where s.agent_name = %s
                order by s.ship_symbol
                """
    return _select_some_ships(db_client, sql, (agent_name,))


def _select_some_ships(db_client: SpaceTradersClient, sql, params):
    connection = db_client.connection
    try:
        rows = try_execute_select(connection, sql, params)
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
            ship.cargo_inventory = []
            # , 6: n.waypoint_symbol, n.departure_time, n.arrival_time, n.origin_waypoint, n.destination_waypoint, n.flight_status, n.flight_mode

            ship.nav = _nav_from_row(row[6:13], db_client)
            ship.frame = _frame_from_row(row[13:24])
            ship.fuel_capacity = row[23]
            ship.fuel_current = row[24]
            ship._cooldown_expiration = row[25]
            ship._cooldown_length = row[26]
            ships[ship.name] = ship
        return ships
    except Exception as err:
        return LocalSpaceTradersRespose(
            error=err,
            status_code=0,
            error_code=0,
            url=f"select_ship._select_ship",
        )


def _select_ship_one(ship_symbol: str, db_client: SpaceTradersClient):
    sql = """select s.ship_symbol, s.agent_name, s.faction_symbol, s.ship_role, s.cargo_capacity, s.cargo_in_use
                , n.waypoint_symbol, n.departure_time, n.arrival_time, n.o_waypoint_symbol, n.d_waypoint_symbol, n.flight_status, n.flight_mode
                , sfl.condition --13
                , sf.frame_symbol, sf.name, sf.description, sf.module_slots, sf.mount_points, sf.fuel_capacity, sf.required_power, sf.required_crew, sf.required_slots
                , s.fuel_capacity, s.fuel_current --24  
                , sc.expiration, sc.total_seconds --26
                from ships s join ship_nav n on s.ship_symbol = n.ship_symbol
                left join ship_frame_links sfl on s.ship_symbol = sfl.ship_symbol
                left join ship_frames sf on sf.frame_symbol = sfl.frame_symbol
                left join ship_cooldown sc on s.ship_symbol = sc.ship_symbol
                where s.ship_symbol = %s
                """
    return _select_some_ships(db_client, sql, (ship_symbol,))


def _nav_from_row(row, db_client: SpaceTradersClient) -> ShipNav:
    """
    expected:
    0: n.waypoint_symbol,
    1: n.departure_time,
    2: n.arrival_time,
    3: n.origin_waypoint,
    4: n.destination_waypoint,
    5: n.flight_status,
    6: n.flight_mode

    """
    current_waypoint = db_client.waypoints_view_one("", row[0])
    if not current_waypoint:
        current_waypoint = None

    origin = db_client.waypoints_view_one("", row[3])
    if not origin:
        origin = None
    destination = db_client.waypoints_view_one("", row[4])
    if not destination:
        destination = None

    return_obj = ShipNav(
        current_waypoint.system_symbol,
        current_waypoint.symbol,
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
        row[1],
        row[2],
        row[5],
        row[6],
    )
    # SHIP NAV ENDS

    return return_obj


def _frame_from_row(row) -> ShipFrame:
    """



    0: sf.frame_symbol,
    1: sf.name,
    2: sf.description,
    3: sf.module_slots,
    4: sf.mount_points,
    5: sf.fuel_capacity,
    6: sf.required_power,
    7: sf.required_crew,
    8: sf.required_slots,
    9: s.fuel_capacity,
    10: s.fuel_current,
    11: sfl.condition

    """

    ##crew moduels power
    reqiurements = ShipRequirements(row[8], row[9], row[7])
    return_obj = ShipFrame(
        row[1], row[2], row[3], row[4], row[5], row[6], row[0], reqiurements
    )

    return return_obj
