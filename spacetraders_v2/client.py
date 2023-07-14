from typing import Protocol


class SpaceTradersClient(Protocol):
    token: str = None

    def __init__(self, token) -> None:
        self.token = token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def update(self, json_data: dict):
        pass
