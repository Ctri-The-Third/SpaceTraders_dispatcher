import pytest

from spacetraders_v2.spacetraders import SpaceTraders


def test_game_status():
    st = SpaceTraders()
    status = st.game_status()

    assert status.status == "SpaceTraders is currently online and available to play"
