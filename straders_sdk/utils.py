import requests
import logging
import urllib.parse
from dataclasses import dataclass
from logging import FileHandler, StreamHandler
from sys import stdout
from datetime import datetime
import random
import time
from .local_response import LocalSpaceTradersRespose

st_log_client: "SpaceTradersClient" = None
ST_LOGGER = logging.getLogger("API-Client")
SEND_FREQUENCY = 0.33  # 3 requests per second
SEND_FREQUENCY_VIP = 3  # for every X requests, 1 is a VIP.  to decrease the number of VIP allocations, increase this number.
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

SURVEYOR_SYMBOLS = ["MOUNT_SURVEYOR_I", "MOUNT_SURVEYOR_II", "MOUNT_SURVEYOR_III"]
ERRROR_COOLDOWN = 4000
from .responses import RemoteSpaceTradersRespose, SpaceTradersResponse


@dataclass
class ApiConfig:
    __instance = None
    base_url: str = "https://api.spacetraders.io"
    version: str = "v2"

    def __new__(cls, base_url=None, version=None):
        if cls.__instance is None:
            cls.__instance = super(ApiConfig, cls).__new__(cls)

        return cls.__instance

    def __init__(self, base_url=None, version=None):
        if base_url:
            self.base_url = base_url
        if version:
            self.version = version


def get_and_validate_page(
    url, page_number, params=None, headers=None
) -> SpaceTradersResponse or None:
    params = params or {}
    params["page"] = page_number
    params["limit"] = 20
    return get_and_validate(url, params=params, headers=headers)


def get_and_validate_paginated(
    url, per_page: int, page_limit: int, params=None, headers=None
) -> SpaceTradersResponse or None:
    params = params or {}
    params["limit"] = per_page
    data = []
    for i in range(1, page_limit or 1):
        params["page"] = i
        response = get_and_validate(url, params=params, headers=headers)
        if response and response.data:
            data.extend(response.data)
        elif response:
            response.data = data
            return response
        else:
            return response
        if page_limit >= 10:
            sleep(1)
    response.data = data
    return response


def get_and_validate(
    url, params=None, headers=None, pages=None, per_page=None
) -> SpaceTradersResponse or None:
    "wraps the requests.get function to make it easier to use"
    resp = False
    while not resp:
        time.sleep(
            max(
                singleton_next_available_request.get_instance().seconds_until_slot(vip),
                0,
            )
        )

        try:
            response = requests.get(url, params=params, headers=headers, timeout=5)
        except (
            requests.exceptions.ConnectionError,
            TimeoutError,
            TypeError,
            TimeoutError,
            requests.ReadTimeout,
        ) as err:
            logging.error("ConnectionError: %s, %s", url, err)
            return LocalSpaceTradersRespose(
                "Could not connect!! network issue?", 404, 0, url
            )

        except Exception as err:
            logging.error("Error: %s, %s", url, err)
        _log_response(response)
        if response.status_code == 429:
            if st_log_client:
                st_log_client.log_429(url, RemoteSpaceTradersRespose(response))
            logging.warning("Rate limited retrying!")

            continue
        if response.status_code >= 500 and response.status_code < 600:
            logging.error(
                "SpaceTraders Server error: %s, %s", url, response.status_code
            )
        return RemoteSpaceTradersRespose(response)


def rate_limit_check(response: requests.Response):
    if response.status_code != 429:
        return


def request_and_validate(method, url, data=None, json=None, headers=None):
    if method == "GET":
        return get_and_validate(url, params=data, headers=headers)
    elif method == "POST":
        return post_and_validate(url, data=data, json=json, headers=headers)
    elif method == "PATCH":
        return patch_and_validate(url, data=data, json=json, headers=headers)
    else:
        return LocalSpaceTradersRespose("Method %s not supported", 0, 0, url)


def post_and_validate(
    url, data=None, json=None, headers=None, vip=False
) -> SpaceTradersResponse:
    "wraps the requests.post function to make it easier to use"

    # repeat 5 times with staggered wait
    # if still 429, skip
    resp = False
    while not resp:
        time.sleep(
            singleton_next_available_request.get_instance().seconds_until_slot(vip)
        )
        try:
            response = requests.post(
                url, data=data, json=json, headers=headers, timeout=5
            )
        except (requests.exceptions.ConnectionError, TimeoutError, TypeError) as err:
            logging.error("ConnectionError: %s, %s", url, err)
            return LocalSpaceTradersRespose(
                "Could not connect!! network issue?", 404, 0, url
            )

        except Exception as err:
            logging.error("Error: %s, %s", url, err)
            return LocalSpaceTradersRespose(f"Could not connect!! {err}", 404, 0, url)
        _log_response(response)
        if response.status_code == 429:
            logging.debug("Rate limited")
            continue
        else:
            return RemoteSpaceTradersRespose(response)
    return LocalSpaceTradersRespose(
        "Unable to do the rate limiting thing, command aborted", 0, 0, url
    )


def patch_and_validate(url, data=None, json=None, headers=None) -> SpaceTradersResponse:
    resp = False
    while not resp:
        time_until_next_slot = (
            datetime.now()
            - singleton_next_available_request.get_instance().seconds_until_slot()
        )
        time.sleep(max(0, time_until_next_slot.total_seconds()))
        try:
            response = requests.patch(
                url, data=data, json=json, headers=headers, timeout=5
            )
        except (requests.exceptions.ConnectionError, TimeoutError) as err:
            logging.error("ConnectionError: %s, %s", url, err)
            return None
        except Exception as err:
            logging.error("Error: %s, %s", url, err)
        _log_response(response)
        if response.status_code == 429:
            logging.warning("Rate limited")
        else:
            return RemoteSpaceTradersRespose(response)


def _url(endpoint) -> str:
    "wraps the `endpoint` in the base_url and version"
    config = ApiConfig()
    return f"{config.base_url}/{config.version}/{endpoint}"


def _log_response(response: requests.Response) -> None:
    "log the response from the server"
    # time, status_code, url, error details if present
    data = response.json() if response.content else {}
    url_stub = urllib.parse.urlparse(response.url).path

    error_text = f" {data['error']['code']}{data['error']}" if "error" in data else ""
    ST_LOGGER.debug("%s %s %s", response.status_code, url_stub, error_text)


def set_logging(level=logging.INFO, filename=None):
    format = "%(asctime)s:%(levelname)s:%(threadName)s:%(name)s  %(message)s"

    log_file = filename if filename else "ShipTrader.log"
    logging.basicConfig(
        handlers=[FileHandler(log_file), StreamHandler(stdout)],
        level=level,
        format=format,
    )
    logging.getLogger("client_mediator").setLevel(logging.DEBUG)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def parse_timestamp(timestamp: str) -> datetime:
    ts = None
    try:
        ts = datetime.fromisoformat(timestamp)
        return ts
    except:
        pass
    for timestamp_format in [DATE_FORMAT, "%Y-%m-%dT%H:%M:%SZ"]:
        try:
            ts = datetime.strptime(timestamp, DATE_FORMAT)
            return ts
        except:
            pass
    if not ts:
        logging.error("Could not parse timestamp: %s", timestamp)
    return ts


def sleep(seconds: int):
    if seconds > 0 and seconds < 6000:
        # ST_LOGGER.info(f"Sleeping for {seconds} seconds")
        time.sleep(seconds)


def sleep_until_ready(ship: "Ship"):
    sleep(max(ship.seconds_until_cooldown, ship.nav.travel_time_remaining))


def waypoint_slicer(waypoint_symbol: str) -> str:
    "returns the system symbol from a waypoint symbol"
    if not waypoint_symbol:
        return None
    pieces = waypoint_symbol.split("-")
    return f"{pieces[0]}-{pieces[1]}"


def try_execute_upsert(connection, sql, params) -> LocalSpaceTradersRespose:
    try:
        cur = connection.cursor()
        cur.execute(sql, params)
        return LocalSpaceTradersRespose(
            None, None, None, url=f"{__name__}.try_execute_upsert"
        )
    except Exception as err:
        logging.error("Couldn't execute upsert: %s", err)
        logging.debug("SQL: %s", sql)
        return LocalSpaceTradersRespose(
            error=err, status_code=0, error_code=0, url=f"{__name__}.try_execute_upsert"
        )


def try_execute_select(connection, sql, params) -> list:
    try:
        cur = connection.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        return rows
    except Exception as err:
        logging.error("Couldn't execute select: %s", err)
        logging.debug("SQL: %s", sql)
        return LocalSpaceTradersRespose(
            error=err, status_code=0, error_code=0, url=f"{__name__}.try_execute_select"
        )


def try_execute_no_results(connection, sql, params) -> LocalSpaceTradersRespose:
    try:
        cur = connection.cursor()
        cur.execute(sql, params)
        return LocalSpaceTradersRespose(
            None, None, None, url=f"{__name__}.try_execute_no_results"
        )
    except Exception as err:
        return LocalSpaceTradersRespose(
            error=err,
            status_code=0,
            error_code=0,
            url=f"{__name__}.try_execute_no_results",
        )


class singleton_next_available_request:
    _instance = None
    _lock = threading.Lock()
    _next_slot = None
    _next_vip_slot = None
    _starting_slot_count = 0
    logger = logging.getLogger("next_available_request")

    @classmethod
    def get_instance(cls):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = singleton_next_available_request()
        return cls._instance

    def __init__(self):
        # Initialize any other instance variables as needed
        self._starting_slot_count = int(
            datetime.now().timestamp() * 1000 / SEND_FREQUENCY
        )
        self._next_slot = datetime.now()
        self._next_vip_slot = datetime.now()

    def seconds_until_slot(self, vip=False):
        with self._lock:
            # find the slot number - which is the system time in ms divided by the send frequency, which is an ms value

            # get the next slot, whether it be a VIP slot or not - which might be now.
            # what if we request a VIP slot and that's in the past, but the lesser slots aren't? we can't send now or we risk a collision. Let's just delay them for the time being.

            # lesser slots only:
            # handle slots in the past
            if not vip:
                return max(self.time_until_normal_slot(), 0)
            if vip:
                return max(self.time_until_vip_slot(), 0)

    def time_until_normal_slot(self) -> float:
        _next_slot_ts = max(self._next_slot, datetime.now())
        slot_count = int(_next_slot_ts.timestamp() / SEND_FREQUENCY)

        _next_slot_count = copy.copy(_next_slot_ts)
        # return value is = _next_slot_ts
        _next_slot_count = slot_count + 1
        if _next_slot_count % SEND_FREQUENCY_VIP == 0:  # it's a VIP slot, next
            _next_slot_count += 1
        self._next_slot = datetime.fromtimestamp((_next_slot_count * SEND_FREQUENCY))
        # self.logger.debug(
        #    "should be sleeping %s seconds",
        #    (self._next_slot - datetime.now()).total_seconds(),
        # )
        return (self._next_slot - datetime.now()).total_seconds()

    def time_until_vip_slot(self) -> float:
        if self._next_slot < self._next_vip_slot:
            return self.time_until_normal_slot()
        _next_slot_ts = max(self._next_vip_slot, datetime.now())
        _next_slot_count = int(_next_slot_ts.timestamp() / SEND_FREQUENCY)

        _next_slot_count += 1
        while _next_slot_count % SEND_FREQUENCY_VIP != 0:
            _next_slot_count += 1
        self._next_vip_slot = datetime.fromtimestamp(
            (_next_slot_count * SEND_FREQUENCY)
        )
        # self.logger.debug(
        #    "should be sleeping %s seconds VIP",
        #    (self._next_slot - datetime.now()).total_seconds(),
        # )

        return (self._next_slot - datetime.now()).total_seconds()
        # if the slot is in the past - send now.
        # if the request is VIP slot is in the future, copy value, increment local value, return copy.

        # we want to execute VIP requests in the first 3rd of a second, and mundane requests in the next 2nd and 3rd of a second. This lines up with our analytics suggesting 2/3rds of requests are non ones.

        # Perform any additional operations on the value if needed
