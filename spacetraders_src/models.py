from dataclasses import dataclass


@dataclass
class User:
    # currently unclear if the response from /my/account is the same as /users/:username
    # will extrapolate into "new user" or "logged in user" depending on which is more appropriate
    username: str
    credits: int
    joined_at = ""
    ships: list = []
    loans: list = []
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
        return cls(
            username=data["username"],
            credits=data["credits"],
            ships=ships,
            loans=loans,
            ship_count=ship_count,
            structure_count=data.get("structureCount", 0),
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
