import subprocess
import logging
import uuid
from spacetraders_src import SpaceTraders
import sys


def main():
    # Create a SpaceTraders instance
    st = SpaceTraders()

    # Get the game status
    status = st.game_status()
    if not status:
        return

    # Claim a username
    username = str(uuid.uuid4())
    resp = st.claim_username(username)
    if not resp:
        # Log an error message with detailed information about the failed claim attempt
        logging.error(
            "Could not claim username %s, %d %s, error code: %s",
            username,
            resp.status_code,
            resp.error,
            resp.error_code,
        )
        return

    print(resp.token)
    print(resp.user)


if __name__ == "__main__":
    # subprocess.call(["setup.bat"], shell=True)
    main()
