import urllib.parse
import logging
import requests
import json
from .utils import get_and_validate, post_and_validate
from .models import *
from .responses import *


class SpaceTraders:
    def __init__(self, base_url="https://api.spacetraders.io", token=None) -> None:
        self.base_url = base_url
        self.token = token
        self.me: User = None
        pass

    def game_status(self) -> GameStatusResponse:
        "/game/status"

        return GameStatusResponse(get_and_validate(f"{self.base_url}/game/status"))

    def claim_username(self, username: str) -> ClaimUsernameResponse:
        "/users/:username/claim"
        username = urllib.parse.quote(username)
        url = f"{self.base_url}/users/{username}/claim"

        resp = ClaimUsernameResponse(post_and_validate(url))
        self.token = resp.token
        return resp

    def my_account(self) -> MyAccountResponse:
        "/my/account"
        url = f"{self.base_url}/my/account"
        resp = MyAccountResponse(get_and_validate(url, headers=self._auth_headers()))
        return resp

    def _auth_headers(self) -> str:
        return {"Authorization": f"Bearer {self.token}"}
