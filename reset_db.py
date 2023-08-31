import psycopg2
import json

confirm = input("Are you sure you want to reset the database? type 'yes' to confirm: ")
if confirm != "yes":
    exit()


user = json.load(open("db.json", "r"))
conn = psycopg2.connect(
    host=user["db_host"],
    port=user["db_port"],
    database=user["db_name"],
    user=user["db_user"],
    password=user["db_password"],
)
cur = conn.cursor()
sql = """

delete from agents;
delete from contract_tradegoods
delete from contracts
delete from jump_gates
delete from jumpgate_connections
--delete from logging
delete from market_tradegood
delete from market_tradegood_listings;
delete from ship_behaviours;
delete from ship_cooldowns;
delete from ship_frame_links;
delete from ship_frames;
delete from ship_mount_links;
delete from ship_mounts;
delete from ship_nav;
delete from ship_tasks;
delete from ships;
delete from shipyard_types;
delete from survey_deposits;
delete from surveys;
delete from systems;
delete from transactions;
delete from waypoint_Charts;
delete from waypoint_Traits;
delete from waypoints;
"""
result = cur.execute(sql)
print(result)
