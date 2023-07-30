import pytest

from straders_sdk.client_mediator import SpaceTradersMediatorClient as SpaceTraders


def test_game_status():
    st = SpaceTraders()
    status = st.game_status()

    assert status.status == "SpaceTraders is currently online and available to play"
