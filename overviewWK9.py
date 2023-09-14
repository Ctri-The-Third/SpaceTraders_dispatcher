# display commanders & their contract progress

# display ships & behaviours

# display discovered shipyards & market info (if available)
import pandas as pd
import markdown
import psycopg2
from time import sleep
import json
from straders_sdk.utils import try_execute_select
from flask import Flask, request
import math
from datetime import datetime

config_file_name = "user.json"
saved_data = json.load(open(config_file_name, "r+"))
db_host = saved_data.get("db_host", None)
db_port = saved_data.get("db_port", None)
db_name = saved_data.get("db_name", None)
db_user = saved_data.get("db_user", None)
db_pass = saved_data.get("db_pass", None)

connection = psycopg2.connect(
    host=db_host, port=db_port, database=db_name, user=db_user, password=db_pass
)
connection.autocommit = True
cursor = connection.cursor()

agent_str = """
<title> Agents overview </title>
%s\n%s

# Commanders & contracts

<div markdown = block>%s</div>
<div markdown = block>%s</div>
<div markdown = block>%s</div>


%s
"""

ship_str = """
<title> Ships overview</title>
%s\n%s
# Ships & behaviours
%s

%s"""

analytics_str = """
<title> Analytics </title>
%s\n%s
# Analytics
%s

%s

%s

%s"""


def perf_behaviour():
    sql = """select activity_window, behaviour_id, sessions, earnings, requests, cpr, bhvr_cph from behaviour_performance;"""
    rows = try_execute_select(connection, sql, ())
    if not rows:
        return ""

    out_str = """
## Behaviour performance  \n
| activity_window | behaviour_id | sessions | earnings | requests | cpr | bhvr_cph |
| --- | --- | --- | --- | --- | --- | --- |\n"""
    for row in rows:
        out_str += f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} | {row[6]} |\n"
    return out_str


def perf_sessions():
    sql = """select activity_time, agent_name, earnings, requests, delayed_requests, cpr from session_stats_per_hour
order by agent_name;
"""
    rows = try_execute_select(connection, sql, ())
    if not rows:
        return ""

    out_str = """## Session performance  \n
| activity_time | agent_name | earnings | requests | delayed_requests | cpr |
| --- | --- | --- | --- | --- | --- |"""
    for row in rows:
        out_str += (
            f"\n| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} |  "
        )
    return out_str


def perf_shipy_types():
    sql = """
select agent_name, shipyard_type, best_price, count_of_ships
, earnings, requests, sessions
, round(cph,2) as cph_per_ship, round(cpr,2) as total_cpr
from shipyard_type_performance
order by agent_name, cph desc"""
    rows = try_execute_select(connection, sql, ())
    if not rows:
        return ""
    out_str = """## Shipyard performance  \n
| agent_name | shipyard_type | best_price | count_of_ships | earnings | requests | sessions | cph_per_ship | total_cpr |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"""
    for row in rows:
        out_str += f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} | {row[6]} | {row[7]} | {row[8]} |\n"
    return out_str


def transaction_summary():
    sql = """select agent_name, credits_earned as cr, utilisation as util, event_hour 
    from agent_credits_per_hour 
    where event_hour >= now() at time zone 'utc' - interval '8 hours'
    order by event_hour desc, agent_name asc
"""
    rows = try_execute_select(connection, sql, ())
    df = pd.DataFrame(rows, columns=["agent_name", "cr", "util", "event_hour"])
    pivot_df = pd.pivot(
        index="event_hour",
        columns="agent_name",
        values=["cr", "util"],
        data=df,
    )
    out_str = pivot_df.to_markdown()
    return out_str


link_pieces = """<table><tr>
     <td> <a href = "/"> agents </a> </td>
     <td> <a href = "/ships"> ships </a> </td>
     <td> <a href = "/sessions"> sessions </a> </td>
    </tr></table>"""


def scan_progress():
    sql = """ 
            select *, 1 from waypoints_not_scanned_progress 
            union
            select *, 2 from jumpgates_scanned_progress
            union 
            select *, 3 from mkt_shpyrds_waypoints_scanned_progress
            union
            select *, 4 from  mkt_shpyrds_systems_visit_progress
            order by 5
            """
    rows = try_execute_select(connection, sql, ())
    output = """| Search | Scanned | Total | Progress |
                | ------ | ----- | ------- | -------- |"""
    if not rows:
        output += "\n| got an error checking on the scans |"
        return output
    for row in rows:
        output += f"\n| {row[0]} | {row[1]} | {row[2]} | {row[3]}% |"

    return output


def commander_overview():
    sql = """select ao.agent_symbol, ao.credits, ao.starting_faction, ao.ship_count, trade_symbol, units_fulfilled, units_required , progress, ao.last_updated 
            from agent_overview ao 
            join contracts_overview co on ao.agent_symbol = co.agent_symbol 
            order by last_updated desc"""
    cursor.execute(sql)
    rows = cursor.fetchall()
    response = ""
    if len(rows) > 0:
        response = "| Agent | Credits | faction | ships | contract for | quantities | progress | last_updated |\n"
        response += "| ---  |     --- |     --- | ---   |          --- |  ----             |  ---     |    ---       |\n"
    for row in rows:
        response += f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |  {row[4]} | {row[5]} / {row[6]} | {row[7]}% | {row[8]} |\n"
    return response


def ship_overview(ship_id):
    sql = """select agent_name, ship_symbol
, ship_role
, frame_symbol
, waypoint_symbol
, cargo_in_use
, cargo_capacity
, behaviour_id
, last_updated 
, cooldown_nav
, behaviour_params
from ship_overview
where ship_symbol = %s
order by agent_name, ship_role, frame_symbol, ship_symbol

    """
    rows = try_execute_select(connection, sql, (ship_id,))

    output_str = f"""

## Ship {ship_id} 

* {map_frame(rows[0][3])} {rows[0][3]} 

* {map_role(rows[0][2])} {rows[0][2]} 

* Cargo: {map_cargo_percents(rows[0][5],rows[0][6])} {rows[0][5]} / {rows[0][6]}

* Waypoint: {rows[0][4]} 

* Behaviour_id: {rows[0][7]} 

* Behaviour_params {rows[0][10]}

## logs 
"""

    sql = """SELECT 
  date_trunc('second', event_timestamp) AS event_timestamp,
  event_name,
  event_params,
  status_code,
  round(duration_seconds,2) AS request_delay,
  round(EXTRACT(epoch FROM (
     event_timestamp - 
    LAG( event_timestamp) OVER (ORDER BY event_timestamp asc)
  ))::numeric,2) AS process_delay
FROM logging 
WHERE 
  ship_symbol = %s
  AND event_timestamp >= NOW() AT TIME ZONE 'utc' - INTERVAL '1 day'
ORDER BY event_timestamp DESC;
"""
    rows = try_execute_select(connection, sql, (ship_id,))

    output_str += """
    
| datetime | request | execution | event_name | event_params |  
| --- | --- | --- | --- | --- |   \n"""
    for row in rows:
        output_str += f"| {datetime.strftime(row[0],'%H:%M:%S')} |{row[4] or 0 }s | {row[5] or 0}s  | {row[1]} | {row[3]} {row[2]} |\n"

    return output_str


def ships_overview(ship_id=None):
    if ship_id:
        return ship_overview(ship_id)
    sql = """select agent_name, ship_symbol
, ship_role
, frame_symbol
, waypoint_symbol
, cargo_in_use
, cargo_capacity
, behaviour_id
, last_updated 
, cooldown_nav
from ship_overview
where locked_until > now() at time zone 'utc'
order by agent_name, ship_role, frame_symbol, ship_symbol
    """

    cargo_percents = {
        0: "🌑🌑",
        1: "🌘🌑",
        2: "🌗🌑",
        3: "🌖🌑",
        4: "🌕🌒",
        5: "🌕🌓",
        6: "🌕🌔",
        7: "🌕🌕",
    }

    rows = try_execute_select(connection, sql, ())
    response = ""
    last_agent = ""
    shipyard_type_counts = {}
    agent_ships = 0
    active_ships = 0
    response_block = """"""

    if len(rows) > 0:
        rows.append(["", "", "", "", "", 0, 0, "", "", ""])
        for row in rows:
            if row[0] != last_agent:
                # only print the header row if this is not the first pass through
                # the header row gets added at the end of the loop
                if last_agent != "":
                    header_block = f"""\n\n### {last_agent}\n
* {last_agent} has {agent_ships} ships, {active_ships} active ({round(active_ships/agent_ships*100,2)}%)\n"""

                    for key, value in shipyard_type_counts.items():
                        header_block += f"* {key}: {value}\n"
                    response += header_block + agent_block + "\n\n"
                last_agent = row[0]
                agent_block = """"""
                shipyard_type_counts = {}
                agent_ships = 0
                active_ships = 0
            busy_emoji = "✅" if row[9] else "❌"
            frame_emoji = map_frame(row[3])
            role_emoji = map_role(row[2])
            cargo_emoji = map_cargo_percents(row[5], row[6])
            shipyard_type_counts[f"{frame_emoji}{role_emoji}"] = (
                shipyard_type_counts.get(f"{frame_emoji}{role_emoji}", 0) + 1
            )
            agent_ships += 1
            if row[9]:
                active_ships += 1

            agent_block += f'[{busy_emoji}](/ships?id={row[1]} "{row[1]}{frame_emoji}{role_emoji}{cargo_emoji}") '
    return response


def map_role(role) -> str:
    roles = {
        "COMMAND": "👑",
        "EXCAVATOR": "⛏️",
        "HAULER": "🚛",
        "SATELLITE": "🛰️",
        "REFINERY": "⚙️",
    }
    return roles.get(role, role)


def map_frame(role) -> str:
    frames = {
        "FRAME_DRONE": "⛵",
        "FRAME_PROBE": "⛵",
        "FRAME_MINER": "🚤",
        "FRAME_LIGHT_FREIGHTER": "🚤",
        "FRAME_FRIGATE": "🚤",
        "FRAME_HEAVY_FREIGHTER": "⛴️",
    }
    return frames.get(role, role)


def map_cargo_percents(cargo_in_use, cargo_capacity) -> str:
    cargo_percents = {
        0: "\U0001F311\U0001F311",
        1: "\U0001F318\U0001F311",
        2: "\U0001F317\U0001F311",
        3: "\U0001F316\U0001F311",
        7: "\U0001F316\U0001F315",
        6: "\U0001F316\U0001F314",
        5: "\U0001F316\U0001F313",
        4: "\U0001F316\U0001F312",
    }
    return cargo_percents.get(
        math.floor((cargo_in_use / max(cargo_capacity, 1)) * 8), "\U0001F311"
    )


css_blob = """
<style>
body {
font-family: "Lucida Console", Courier, monospace;
background-color:#222;
color: #3f3;
}
table {
border: 1px solid green;
}
td {
padding:2px;
padding-right:10px;
}

a { color: #3f3; text-decoration: none; }
</style>
"""

javascript_refresh_blob = """
<script>
setTimeout(function(){
    window.location.reload(1);
}, 15000);
</script>
"""


def out_to_file(str, filename):
    str = markdown.markdown(str, extensions=["tables", "md_in_html"])
    file = open(filename, "w+", encoding="utf-8")
    file.write(str)
    file.close()


app = Flask(__name__)


@app.route("/")
def index():
    out_str = markdown.markdown(
        agent_str
        % (
            css_blob,
            link_pieces,
            commander_overview(),
            scan_progress(),
            transaction_summary(),
            javascript_refresh_blob,
        ),
        extensions=["tables", "md_in_html"],
    )
    return out_str


@app.route("/refresh")
def refresh():
    sql = "refresh materialized view mat_session_stats;"
    try_execute_select(connection, sql, ())
    return "refreshed. go back to index."


@app.route("/ships/")
def ships():
    param_value = request.args.get("id", None)
    out_str = markdown.markdown(
        ship_str
        % (
            css_blob,
            link_pieces,
            ships_overview(param_value),
            javascript_refresh_blob,
        ),
        extensions=["tables", "md_in_html"],
    )
    return out_str


@app.route("/sessions/")
def analytics():
    formatted_analytics = analytics_str % (
        css_blob,
        link_pieces,
        perf_sessions(),
        perf_shipy_types(),
        perf_behaviour(),
        "",  # javascript_refresh_blob,
    )
    out_str = markdown.markdown(
        formatted_analytics,
        extensions=["tables", "md_in_html"],
    )
    return out_str


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4000)
