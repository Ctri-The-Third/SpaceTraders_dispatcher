from datetime import datetime, timedelta
import logging
import json
from time import sleep

import psycopg2.sql


from straders_sdk.local_response import LocalSpaceTradersRespose
from straders_sdk.models import Shipyard, ShipyardShip, Waypoint, Agent
from straders_sdk.ship import Ship
from straders_sdk.client_mediator import SpaceTradersMediatorClient as SpaceTraders
from straders_sdk.contracts import Contract

from straders_sdk.utils import (
    set_logging,
    waypoint_slicer,
    try_execute_select,
    try_execute_upsert,
)
from dispatcherWK12 import (
    BHVR_EXTRACT_AND_SELL,
    BHVR_RECEIVE_AND_FULFILL,
    BHVR_RECEIVE_AND_REFINE,
)

from conductor_functions import (
    process_contracts,
    get_prices_for,
    set_behaviour,
    maybe_buy_ship_hq_sys,
    log_task,
)


logger = logging.getLogger(__name__)


class Conductor:

    """This class will manage the recon agents and their behaviour."""

    def __init__(
        self,
    ) -> None:
        self.current_agent_symbol = user.get("agents")[0]["username"]
        self.current_agent_token = user.get("agents")[0]["token"]

        client = self.st = SpaceTraders(
            self.current_agent_token,
            db_host=user["db_host"],
            db_port=user["db_port"],
            db_name=user["db_name"],
            db_user=user["db_user"],
            db_pass=user["db_pass"],
            current_agent_symbol=self.current_agent_symbol,
        )
        self.connection = client.db_client.connection
        self.asteroid_wp: Waypoint = None
        self.haulers = []
        self.commanders = []
        self.hounds = []
        self.extractors = []
        self.surveyors = []
        self.ships_we_might_buy = []
        self.satellites = []
        self.refiners = []

    def run(self):
        #
        # * scale regularly and set defaults
        # * progress missions
        last_hourly_update = datetime.now() - timedelta(hours=2)
        last_daily_update = datetime.now() - timedelta(days=2)
        #
        # hourly calculations of profitable things, assign behaviours and tasks
        #
        while True:
            self.populate_ships()
            # daily reset uncharted waypoints.

            if last_daily_update < datetime.now() - timedelta(days=1):
                self.daily_update()

            if last_hourly_update < datetime.now() - timedelta(hours=1):
                self.hourly_update()

            self.minutely_update()
            sleep(60)

    def hourly_update(self):
        st = self.st

        hq = st.view_my_self().headquarters
        hq_sys = waypoint_slicer(hq)
        resp = st.find_waypoints_by_type_one(hq_sys, "ASTEROID_FIELD")
        self.asteroid_wp = resp

        # determine current starting asteroid
        # determine top 2 goods to export
        # assign a single trader to buy/sell behaviour
        # assign a single extractor to extract/sell locally
        # assign a single extractor to extract/sell remotely
        # if there is a refiner, assign a single extractor to extract/transfer

        # how do we decide on surveyors?

    def daily_update(self):
        sql = """
            update waypoints w set checked = false where waypoint_symbol in (
                select waypoint_symbol from waypoint_traits wt where wt.trait_symbol = 'UNCHARTED'
            );
            delete from waypoint_traits WT where wt.trait_symbol = 'UNCHARTED';"""
        try_execute_upsert(self.connection, sql, [])

    def minutely_update(self):
        """This method handles ship scaling and assigning default behaviours."""
        st = self.st

        st.current_agent = st.view_my_self()

        process_contracts(self.st)
        hounds = self.hounds
        refiners = self.refiners
        haulers = self.haulers
        #
        # this can be its own "scale up" method
        #
        behaviour_params = {"asteroid_wp": self.asteroid_wp.symbol}
        # stage
        if len(hounds) < 50:
            new_ship = maybe_buy_ship_hq_sys(st, "SHIP_ORE_HOUND")
            new_behaviour = BHVR_EXTRACT_AND_SELL
            self.ships_we_might_buy = ["SHIP_ORE_HOUND"]
        # stage 4
        elif len(hounds) <= 50 or len(refiners) < 1 or len(haulers) < 3:
            self.ships_we_might_buy = [
                "SHIP_PROBE",
                "SHIP_ORE_HOUND",
                "SHIP_HEAVY_HAULER",
                "SHIP_COMMAND_FRIGATE",
                "SHIP_REFINERY",
            ]
            if len(hounds) < 50:
                new_ship = False  # maybe_buy_ship_hq_sys(st, "SHIP_ORE_HOUND")
                new_behaviour = BHVR_EXTRACT_AND_SELL
            elif len(refiners) < 2:
                new_ship = maybe_buy_ship_hq_sys(st, "SHIP_REFINERY")
                new_behaviour = BHVR_RECEIVE_AND_REFINE
            elif len(haulers) < 10:
                new_ship = maybe_buy_ship_hq_sys(st, "SHIP_HEAVY_HAULER")
                new_behaviour = BHVR_RECEIVE_AND_FULFILL
            pass

        if new_ship:
            set_behaviour(
                self.connection,
                new_ship.name,
                new_behaviour,
                behaviour_params=behaviour_params,
            )
            self.populate_ships()

        self.maybe_upgrade_ship()

    def maybe_upgrade_ship(self):
        # surveyors first, then extractors
        max_mining_strength = 60
        max_survey_strength = self.max_survey_strength() * 3
        best_surveyor = (
            "MOUNT_SURVEYOR_I" if max_survey_strength == 3 else "MOUNT_SURVEYOR_II"
        )
        if not clear_to_upgrade(self.st.view_my_self(), self.connection):
            return
        ship_to_upgrade = None
        price = get_prices_for(self.connection, best_surveyor)[0] * 3
        for ship in self.surveyors:
            ship: Ship
            if ship.survey_strength <= max_survey_strength:
                outfit_symbols = [best_surveyor, best_surveyor, best_surveyor]
                ship_to_upgrade = ship
                break

        if not ship_to_upgrade:
            for ship in self.extractors:
                ship: Ship
                if ship.extract_strength <= max_mining_strength:
                    outfit_symbols = [
                        "MOUNT_MINING_LASER_II",
                        "MOUNT_MINING_LASER_II",
                        "MOUNT_MINING_LASER_I",
                    ]
                    ship_to_upgrade = ship
                    break
        if not ship_to_upgrade:
            return

        params = {"mounts": outfit_symbols}
        if self.st.view_my_self().credits < price:
            return
        log_task(
            self.connection,
            "UPGRADE_TO_SPEC",
            [],
            ship_to_upgrade.nav.system_symbol,
            1,
            self.st.current_agent_symbol,
            params,
            specific_ship_symbol=ship_to_upgrade.name,
        )

    def max_mining_strength(self):
        sql = """select * from market_prices
where trade_symbol ilike 'mount_mining_laser%'"""
        results = try_execute_select(self.connection, sql, ())
        symbols = [row[0] for row in results]
        if "MOUNT_MINING_LASER_II" in symbols:
            return 25
        elif "MOUNT_MINING_LASER_I" in symbols:
            return 10

    def max_survey_strength(self):
        sql = """select * from market_prices
where trade_symbol ilike 'mount_surveyor_%%'"""
        results = try_execute_select(self.connection, sql, [])
        symbols = [row[0] for row in results]
        if "MOUNT_SURVEYOR_II" in symbols:
            return 2
        elif "MOUNT_SURVEYOR_I" in symbols:
            return 1

    def populate_ships(self):
        "Set the conductor's ship lists, and subdivides them into roles."
        ships = self.st.ships_view()
        self.satellites = [ship for ship in ships.values() if ship.role == "SATELLITE"]
        self.haulers = [ship for ship in ships.values() if ship.role == "HAULER"]
        self.haulers.sort(key=lambda ship: ship.index)
        self.commanders = [ship for ship in ships.values() if ship.role == "COMMAND"]
        self.commanders.sort(key=lambda ship: ship.index)
        hounds = [ship for ship in ships.values() if ship.frame.symbol == "FRAME_MINER"]
        hounds.sort(key=lambda ship: ship.index)
        # for every 6.6667 hounds, make one a surveyor. ignore the first one.
        self.surveyors = hounds[1::6]

        # extractors are all hounds that aren't surveyors
        self.extractors = [ship for ship in hounds if ship not in self.surveyors]

        self.refiners = [ship for ship in ships.values() if ship.role == "REFINERY"]


def clear_to_upgrade(agent: Agent, connection) -> bool:
    """checks whether or not there's an open upgrade task.
    If the agent has more than a million credits, this will always return true."""
    if agent.credits >= 1000000:
        return True

    sql = """select * from ship_tasks
where behaviour_id = 'UPGRADE_TO_SPEC' and (not completed or completed is null)
and agent_symbol = %s"""
    rows = try_execute_select(connection, sql, (agent.symbol,))
    return len(rows)


if __name__ == "__main__":
    set_logging()
    user = json.load(open("user.json"))
    logger.info("Starting up conductor, preparing to connect to database")
    logger.info("Connected to database")
    agents = []
    agents_and_clients: dict[str:SpaceTraders] = {}
    Conductor().run()
