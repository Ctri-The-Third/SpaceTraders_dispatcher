from .utils import get_and_validate, post_and_validate
from .responses import GameStatusResponse, SpaceTradersResponse, RegistrationResponse
from .responses import MyAgentResponse

# Attempted relative import beyond top-level packagePylintE0402:relative-beyond-top-level


class SpaceTraders:
    """SpaceTraders API client."""

    def __init__(self, token=None, base_url=None, version=None) -> None:
        self.token = token
        self.base_url = "https://api.spacetraders.io" if base_url is None else base_url
        self.version = "v2" if version is None else version

        status = self.game_status()

        if not status:
            raise Exception(f"Could not connect to SpaceTraders server: {status.error}")
        pass

        self.announcements = status.announcements
        self.next_reset = status.next_reset

    def game_status(self) -> GameStatusResponse:
        """Get the status of the SpaceTraders game server."""
        url = self._url("")
        resp = get_and_validate(url)
        return GameStatusResponse(resp)

    def register(self, callsign, faction="COSMIC", email=None):
        """Register a new user."""
        url = self._url("register")
        data = {"symbol": callsign, "faction": faction}
        if email is not None:
            data["email"] = email
        resp = RegistrationResponse(post_and_validate(url, data))
        self.token = resp.token
        return resp

    def view_self(self):
        """view the current agent"""
        url = self._url("my/agent")
        resp = get_and_validate(url, headers=self._headers())
        return MyAgentResponse(resp)

    def _url(self, endpoint):
        return f"{self.base_url}/{self.version}/{endpoint}"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}
