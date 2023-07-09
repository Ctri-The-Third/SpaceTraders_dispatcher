import requests
import logging
import urllib.parse

ST_LOGGER = logging.getLogger("SpaceTradersAPI")
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

# todo - add a handler for 429 and 502 errors


def get_and_validate(url, params=None, headers=None) -> requests.Response or None:
    "wraps the requests.get function to make it easier to use"
    try:
        response = requests.get(url, params=params, headers=headers, timeout=5)
        response: requests.Response
    except requests.exceptions.ConnectionError as err:
        logging.error("ConnectionError: %s, %s", url, err)
        return None

    return response


def post_and_validate(
    url, data=None, json=None, headers=None
) -> requests.Response or None:
    "wraps the requests.post function to make it easier to use"

    try:
        response = requests.post(url, data=data, json=json, headers=headers, timeout=5)
        response: requests.Response
    except requests.exceptions.ConnectionError as err:
        logging.error("ConnectionError: %s, %s", url, err)
        return None
    except Exception as err:
        logging.error("Error: %s, %s", url, err)
        raise Exception from err

    return response
