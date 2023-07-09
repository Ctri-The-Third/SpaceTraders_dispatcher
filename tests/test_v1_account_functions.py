from spacetraders_v1 import SpaceTraders
import uuid

TEST_TOKEN = "fd3c9cbf-7cc9-45be-b5e5-43a4153f5c35"


def test_online():
    st = SpaceTraders()
    status = st.game_status()


def test_claim_username():
    st = SpaceTraders()
    status = st.game_status()
    assert status is not None

    username = str(uuid.uuid4())
    resp = st.claim_username(username)
    assert resp
    assert resp.token is not None
    assert resp.user is not None


def test_my_account():
    st = SpaceTraders(token=TEST_TOKEN)
    resp = st.my_account()
    assert resp.user is not None


def test_my_account_no_token():
    st = SpaceTraders()
    resp = st.my_account()
    assert not resp
