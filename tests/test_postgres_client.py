import os
import psycopg2
from spacetraders_v2.client_postgres import SpaceTradersPostgresClient


def test_connection():
    conn = psycopg2.connect(
        host=DB_HOST_NAME, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("SELECT * FROM public.waypoints")
