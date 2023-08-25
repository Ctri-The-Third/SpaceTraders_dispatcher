import sys

sys.path.append(".")

from straders_sdk.utils import set_logging
import threading
import time
import requests_ratelimiter
import random
from straders_sdk.client_api import SpaceTradersApiClient
import logging


def test_multiple_API_clients():
    set_logging(logging.DEBUG)
    session = requests_ratelimiter.LimiterSession(per_second=3)
    client = SpaceTradersApiClient(
        "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZGVudGlmaWVyIjoiQ1RSSS1MOC0iLCJ2ZXJzaW9uIjoidjIiLCJyZXNldF9kYXRlIjoiMjAyMy0wOC0xOSIsImlhdCI6MTY5MjQ2NjE3OSwic3ViIjoiYWdlbnQtdG9rZW4ifQ.J3qVjsZ71zaxadLXNm5n8ySNtW9JZQhexDO1OrPqLETl9VtFiGrxtSkeZVeFMmAzmPhU3CsCnMdVrrarUwn-N7vdDZ_SvYXMUNJBXZnJauQoCvDPzVPx-3MrEOw7Cq5v_JmfWyO8bTNU4-Au7pHKUyzMRGKpP0ePey7LVjd0s66Cw6SwVtttCmSUqEQKlHr88V0_iXDwPHSjEWKuOeFaNmD4JG7UKABt8Fhf0BO-hVTkfDDW5i0SrwdsJxgdGUyzUv0YhD4bI5Y7-7kygi1-lnkTR9qSA1DIIl4KMfUobJXKnSNPeb9QDvK1giyYj9VlsFbiuE5zCRkP7VfKEFujIg",
        session=session,
    )
    for thread in range(20):
        t = threading.Thread(
            target=client.systems_view_twenty,
            name=f"thread {thread}",
            args=(random.randint(0, 600),),
        )
        t.start()


if __name__ == "__main__":
    test_multiple_API_clients()
