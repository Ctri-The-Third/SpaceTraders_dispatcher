from spacetraders_v2.utils import set_logging
from spacetraders_v2 import SpaceTraders
import sys
import json


def master(st: SpaceTraders):
    wayps = st.systems_list_all(force=True)

    pass


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
        db_port=users["db_port"],
    )
    status = st.game_status()

    master(st)
