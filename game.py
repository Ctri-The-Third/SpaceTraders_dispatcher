import subprocess
import logging
import uuid
from spacetraders_v2.spacetraders import SpaceTraders
import sys
import json


def main():
    # Create a SpaceTraders instance
    st = SpaceTraders()

    # Get the game status
    status = st.game_status()
    if not status:
        return

    user = json.load(open("user.json", "r"))

    # Claim a username
    username = str(uuid.uuid4().hex)[0:14]
    resp = st.register(username, faction=user["faction"], email=user["email"])
    if not resp:
        # Log an error message with detailed information about the failed claim attempt
        logging.error(
            "Could not claim username %s, %d %s \n error code: %s",
            username,
            resp.status_code,
            resp.error,
            resp.error_code,
        )
        return

    print(resp.token)
    print(resp.agent)
    resp = st.view_self()
    print(resp.agent)


if __name__ == "__main__":
    # subprocess.call(["setup.bat"], shell=True)
    main()
