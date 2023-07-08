from dataclasses import dataclass
from datetime import datetime
from .utils import DATE_FORMAT


@dataclass
class User:
    # currently unclear if the response from /my/account is the same as /users/:username
    # will extrapolate into "new user" or "logged in user" depending on which is more appropriate
    username: str
    credits: int
    joined_at: datetime = None
    ships: list = None
    loans: list = None
    ship_count: int = 0
    structure_count: int = 0

    @classmethod
    def from_dict(cls, data: dict):
        ships = []
        ship_count = data.get("shipCount", 0)
        if "ships" in data:
            ships = [Ship.from_dict(ship) for ship in data["ships"]]
            ship_count = len(ships)
        loans = []
        if "loans" in data:
            loans = [Loan.from_dict(loan) for loan in data["loans"]]
        joined_at = (
            datetime.strptime(data["joinedAt"], DATE_FORMAT)
            if "joinedAt" in data
            else ""
        )
        return cls(
            username=data["username"],
            credits=data["credits"],
            ships=ships,
            loans=loans,
            ship_count=ship_count,
            structure_count=data.get("structureCount", 0),
            joined_at=joined_at,
        )


@dataclass
class Ship:
    @classmethod
    def from_dict(cls, data: dict):
        pass


@dataclass
class Loan:
    @classmethod
    def from_dict(cls, data: dict):
        pass
