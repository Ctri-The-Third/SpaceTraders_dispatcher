# this script is designed to be called by the conductor - and assign the behaviour of any ship(s) given to it.
from straders_sdk import SpaceTraders
from straders_sdk.ship import Ship
from behaviours.explore_system import (
    ExploreSystem,
    BEHAVIOUR_NAME as EXPLORE_ONE_SYSTEM,
)
from behaviours.remote_scan_and_survey import (
    RemoteScanWaypoints,
    BEHAVIOUR_NAME as REMOTE_SCAN_AND_SURVEY,
)


def run(client: SpaceTraders, ships: list["Ship"]):
    # do we need to do the system sweep?
    # if yes - put that on the satelite

    if not _have_we_all_the_systems(client):
        return ExploreSystem.run(client)
    # do we need to do the jump-gate sweep? Happens early on.
    # can't do this one yet - need to be able to distinguish charted waypoints from uncharted waypoints.
    # do we need to do the waypoint sweep? Happens early on.

    # if all that's good - next step is go refresh stale systems by distance from HQ.

    pass


def _have_we_all_the_systems(st: SpaceTraders):
    sql = """select count(distinct symbol) from systems"""
    cursor = st.db_client.connection.cursor()
    cursor.execute(sql, ())
    row = cursor.fetchone()
    db_systems = row[0]

    status = st.game_status()
    api_systems = status.total_systems
    return (db_systems >= api_systems, status.total_systems)
