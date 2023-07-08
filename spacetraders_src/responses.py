import json
import requests
from .models import User, Ship, Loan


class _STResponse:
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
        self.error = self._response["error"]["message"]
        self.error_code = self._response["error"]["code"]

    def __bool__(self):
        return self.error_code is None


class GameStatusResponse(_STResponse):
    """/game/status"""

    def parse(self):
        self.status = (
            self._response["status"]
            if self._response
            else "could not connect to space traders"
        )

    def __bool__(self):
        return self.status == "spacetraders is currently online and available to play"


class ClaimUsernameResponse(_STResponse):
    """/users/:username/claim"""

    def parse(self):
        self.token = self._response["token"]
        self.user = User.from_dict(self._response["user"])


class MyAccountResponse(_STResponse):
    """/my/account"""

    def parse(self):
        self.user = User.from_dict(self._response["user"])
