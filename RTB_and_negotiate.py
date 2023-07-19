import sys
import json

from spacetraders_v2 import SpaceTraders
from spacetraders_v2.utils import set_logging, sleep


def master(st: SpaceTraders):
    contracts = st.view_my_contracts()
    for contract in contracts.values():
        if not contract.accepted:
            print("There is a pending contract! Accepted it for you.")
            st.contract_accept(contract.id)
            exit(0)
    ships = st.view_my_ships()
    agent = st.view_my_self()
    ship = ships["CTRI-1"]
    st.ship_move(ship, agent.headquaters)
    sleep(ship.nav.travel_time_remaining + 1)
    new_contract = st.ship_negotiate(ship)
    if new_contract:
        st.contract_accept(new_contract.id)


if __name__ == "__main__":
    tar_username = sys.argv[1] if len(sys.argv) > 1 else None

    out_file = f"procure-quest.log"
    set_logging(out_file)

    with open("user.json", "r") as j_file:
        users = json.load(j_file)
    found_user = users["agents"][0]
    for user in users["agents"]:
        if user["username"] == tar_username:
            found_user = user
    st = SpaceTraders(
        found_user["token"],
        db_host=users["db_host"],
        db_name=users["db_name"],
        db_user=users["db_user"],
        db_pass=users["db_pass"],
    )

    master(st)
