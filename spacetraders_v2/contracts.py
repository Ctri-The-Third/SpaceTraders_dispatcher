from datetime import datetime

from .client_interface import SpaceTradersClient
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


class Contract:
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
    client: SpaceTradersClient = None

    def __init__(
        self,
        json_data: dict,
        client: SpaceTradersClient = None,
        token: str = None,
    ) -> None:
        if token:
            self.token = token
        elif client:
            self.token = client.token
            self.client = client
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

    def deliver(self, ship_symbol, trade_symbol, units, ship_to_update: "Ship"):
        # note - this doesn't update the ship's cargo.
        """/my/contracts/:id/deliver"""
        return self.client.contracts_deliver(self, ship_to_update, trade_symbol, units)

    def fulfill(self):
        """/my/contracts/:contractId/fulfill'"""
        raise NotImplementedError
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
        self.client.update(json_data)
