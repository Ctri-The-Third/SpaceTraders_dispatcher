from datetime import datetime

from .client import SpaceTradersClient
from .utils import DATE_FORMAT, _url, post_and_validate
from .models import SymbolClass
from dataclasses import dataclass
import logging

LOGGER = logging.getLogger("contracts")


@dataclass
class ContractDeliverGood(SymbolClass):
    symbol: str
    destination_symbol: str
    units_required: int
    units_fulfilled: int


# this should probably be its own thing


class Contract(SpaceTradersClient):
    id: str
    faction_symbol: str
    type: str
    deadline: datetime
    payment_upfront: int
    payment_completion: int
    deliverables: list[ContractDeliverGood]
    accepted: bool
    fulfilled: bool
    expiration: datetime
    deadline_for_accept: datetime = None
    token: str = None
    other_client: SpaceTradersClient = None

    def __init__(
        self,
        json_data: dict,
        other_client: SpaceTradersClient = None,
        token: str = None,
    ) -> None:
        if token:
            self.token = token
        elif other_client:
            self.token = other_client.token
            self.other_client = other_client
        else:
            raise ValueError("No token provided")

        self.id = json_data["id"]
        self.faction_symbol = json_data["factionSymbol"]
        self.type = json_data["type"]
        self.deadline = datetime.strptime(json_data["terms"]["deadline"], DATE_FORMAT)
        self.expiration = datetime.strptime(json_data["expiration"], DATE_FORMAT)

        self.deadline_to_accept = (
            datetime.strptime(json_data["deadlineToAccept"], DATE_FORMAT)
            if json_data["deadlineToAccept"] is not None
            else None
        )
        self.payment_upfront = json_data["terms"]["payment"]["onAccepted"]
        self.payment_completion = json_data["terms"]["payment"]["onFulfilled"]
        self.deliverables = [
            ContractDeliverGood(*d.values())
            for d in json_data["terms"].get("deliver", [])
        ]
        self.accepted = json_data["accepted"]
        self.fulfilled = json_data["fulfilled"]

    @classmethod
    def from_json(cls, json_data: dict):
        return cls(json_data)

    def deliver(
        self, ship_symbol, trade_symbol, units, ship_to_update: SpaceTradersClient
    ):
        # note - this doesn't update the ship's cargo.
        """/my/contracts/:id/deliver"""
        url = _url(f"/my/contracts/{self.id}/deliver")
        data = {"shipSymbol": ship_symbol, "tradeSymbol": trade_symbol, "units": units}
        headers = self._headers()
        resp = post_and_validate(url, data, headers=headers)
        if not resp:
            print(f"failed to deliver to contract {resp.status_code}, {resp.error}")
            return resp
        self.update(resp.data)
        ship_to_update.update(resp.data)
        return resp

    def fulfill(self):
        """/my/contracts/:contractId/fulfill'"""
        url = _url(f"/my/contracts/{self.id}/fulfill")
        headers = self._headers()

        resp = post_and_validate(url, headers=headers)
        if not resp:
            logging.warning(
                f"failed to fulfill contract {resp.status_code}, {resp.error}"
            )
            return resp
        self.update(resp.data)

    def update(self, json_data: dict):
        if "contract" in json_data:
            self.__init__(json_data["contract"], token=self.token)
        self.other_client.update(json_data)
