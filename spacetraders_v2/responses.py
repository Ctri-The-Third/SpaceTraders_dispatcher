from datetime import datetime
import requests
from .utils import DATE_FORMAT
from .models import Announement, Agent
from .ship import Ship


class SpaceTradersResponse:
    "base class for all responses"

    def __init__(self, response: requests.Response):
        self._response = response.json()
        self.error = None
        self.status_code = response.status_code
        self.error_code = None
        if "error" in self._response:
            self.error_parse()
        else:
            self.parse()

    def parse(self):
        "takes the response object and parses it into the class attributes"
        pass

    def error_parse(self):
        "takes the response object and parses it an error response was sent"
        self.error = self._response["error"]["message"]
        self.error_code = self._response["error"]["code"]
        if "data" in self._response["error"]:
            self._response["error"]["data"]: dict
            for key, value in self._response["error"]["data"].items():
                self.error += f"\n  {key}: {value}"

    def __bool__(self):
        return self.error_code is None


class GameStatusResponse(SpaceTradersResponse):
    "response from {url}/{version}/"

    def parse(self):
        self.status = self._response["status"]
        self.version = self._response["version"]
        self.reset_date = self._response["resetDate"]
        self.description = self._response["description"]
        self.total_agents = self._response["stats"]["agents"]
        self.total_systems = self._response["stats"]["systems"]
        self.total_ships = self._response["stats"]["ships"]
        self.total_waypoints = self._response["stats"]["waypoints"]
        self.next_reset = datetime.strptime(
            self._response["serverResets"]["next"], DATE_FORMAT
        )
        self.announcements = []
        for announcement in self._response["announcements"]:
            self.announcements.append(
                Announement(
                    len(self.announcements), announcement["title"], announcement["body"]
                )
            )


class RegistrationResponse(SpaceTradersResponse):
    "response from {url}/{version}/register"

    def parse(self):
        self.token = self._response["data"]["token"]
        agent = self._response["data"]["agent"]
        self.agent = Agent(
            agent["accountId"],
            agent["symbol"],
            agent["headquarters"],
            agent["credits"],
            agent["startingFaction"],
        )
        self.ship = Ship(self._response["data"]["ship"])
        self.contract = ""
        self.faction = ""


class MyAgentResponse(SpaceTradersResponse):
    "response from {url}/{version}/my/agent"

    def parse(self):
        data = self._response["data"]
        self.agent = Agent(
            data["accountId"],
            data["symbol"],
            data["headquarters"],
            data["credits"],
            data["startingFaction"],
        )
