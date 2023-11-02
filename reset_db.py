import psycopg2
import json

confirm = input("Are you sure you want to reset the database? type 'yes' to confirm: ")
if confirm != "yes":
    exit()


user = json.load(open("user.json", "r"))
conn = psycopg2.connect(
    host=user["db_host"],
    port=user["db_port"],
    database=user["db_name"],
    user=user["db_user"],
    password=user["db_pass"],
)
conn.autocommit = True
sqls = [
    "delete from agents;",
    "delete from contract_tradegoods;",
    "delete from contracts;",
    "delete from extractions;" "delete from jump_gates;",
    "delete from jumpgate_connections;",
    "delete from market_tradegood;",
    "delete from market_tradegood_listings;",
    "delete from ship_behaviours;",
    "delete from ship_cooldowns;",
    "delete from ship_frame_links;",
    "delete from ship_frames;",
    "delete from ship_mounts;",
    "delete from ship_nav;",
    "delete from ship_tasks;",
    "delete from ships;",
    "delete from shipyard_types;",
    "delete from survey_deposits;",
    "delete from surveys;",
    "delete from systems;",
    "delete from transactions;",
    "delete from waypoint_Charts;",
    "delete from waypoint_Traits;",
    "delete from waypoints;",
    "delete from logging;",
]

for sql in sqls:
    with conn.cursor() as cur:
        result = cur.execute(sql)
        result = 0
        print(f"{sql} - {cur.statusmessage}")

rows = [
    [
        "MOUNT_GAS_SIPHON_I",
        "Gas Siphon I",
        "A basic gas siphon that can extract gas from gas giants and other gas-rich bodies.",
        -1,
        -1,
        -1,
    ],
    [
        "MOUNT_GAS_SIPHON_II",
        "Gas Siphon II",
        "An advanced gas siphon that can extract gas from gas giants and other gas-rich bodies more efficiently and at a higher rate.",
        -1,
        -1,
        -1,
    ],
    [
        "MOUNT_GAS_SIPHON_III",
        "Gas Siphon III",
        "An advanced gas siphon that can extract gas from gas giants and other gas-rich bodies with even greater efficiency and at a higher rate.",
        -1,
        -1,
        -1,
    ],
    [
        "MOUNT_SURVEYOR_I",
        "Surveyor I",
        "A basic survey probe that can be used to gather information about a mineral deposit. Surveys QUARTZ_SAND, SILICON_CRYSTALS, PRECIOUS_STONES, ICE_WATER, AMMONIA_ICE, IRON_ORE, COPPER_ORE, SILVER_ORE, ALUMINUM_ORE, GOLD_ORE, PLATINUM_ORE",
        1,
        2,
        1,
    ],
    [
        "MOUNT_SURVEYOR_II",
        "Surveyor II",
        "An advanced survey probe that can be used to gather information about a mineral deposit with greater accuracy.",
        2,
        -1,
        -1,
    ],
    [
        "MOUNT_SURVEYOR_III",
        "Surveyor III",
        "An advanced survey probe that can be used to gather information about a mineral deposit with even greater accuracy.",
        3,
        -1,
        -1,
    ],
    [
        "MOUNT_SENSOR_ARRAY_I",
        "Sensor Array I",
        "A basic sensor array that improves a ship's ability to detect and track other objects in space.",
        1,
        0,
        1,
    ],
    [
        "MOUNT_SENSOR_ARRAY_II",
        "Sensor Array II",
        "An advanced sensor array that improves a ship's ability to detect and track other objects in space with greater accuracy and range.",
        4,
        2,
        2,
    ],
    [
        "MOUNT_SENSOR_ARRAY_III",
        "Sensor Array III",
        "A powerful sensor array that can be used to scan for nearby objects and resources.",
        -1,
        -1,
        -1,
    ],
    [
        "MOUNT_MINING_LASER_I",
        "Mining Laser I",
        "A basic mining laser that can be used to extract valuable minerals from asteroids and other space objects.",
        3,
        0,
        1,
    ],
    [
        "MOUNT_MINING_LASER_II",
        "Mining Laser II",
        "An advanced mining laser that is more efficient and effective at extracting valuable minerals from asteroids and other space objects.",
        5,
        2,
        2,
    ],
    [
        "MOUNT_MINING_LASER_III",
        "Mining Laser III",
        "An advanced mining laser that is even more efficient and effective at extracting valuable minerals from asteroids and other space objects.",
        -1,
        -1,
        -1,
    ],
    [
        "MOUNT_LASER_CANNON_I",
        "Laser Cannon",
        "A basic laser weapon that fires concentrated beams of energy at high speed and accuracy.",
        -1,
        1,
        2,
    ],
    [
        "MOUNT_MISSILE_LAUNCHER_I",
        "Missile Launcher",
        "A basic missile launcher that fires guided missiles with a variety of warheads for different targets.",
        -1,
        2,
        1,
    ],
    [
        "MOUNT_TURRET_I",
        "Rotary Cannon",
        "A rotary cannon is a type of mounted turret that is designed to fire a high volume of rounds in rapid succession.",
        -1,
        1,
        2,
    ],
]

sql = """INSERT INTO public.ship_mounts(
mount_symbol, mount_name, mount_desc, strength, required_crew, required_power)
VALUES (%s, %s, %s, %s, %s, %s)

on conflict (mount_symbol) do nothing;"""
for mount in rows:
    with conn.cursor() as cur:
        result = cur.execute(sql, mount)
        print(f"{mount} - {cur.statusmessage}")
