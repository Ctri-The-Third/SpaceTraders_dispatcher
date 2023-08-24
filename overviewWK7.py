# display commanders & their contract progress

# display ships & behaviours

# display discovered shipyards & market info (if available)
import pandas as pd
import markdown
import psycopg2
from time import sleep
import json
from straders_sdk.utils import try_execute_select
from flask import Flask


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
    sql = """select agent_name, credits_earned, event_hour 
    from agent_credits_per_hour 
    where event_hour >= now() at time zone 'utc' - interval '8 hours'
    order by event_hour desc, agent_name asc
"""
    rows = try_execute_select(connection, sql, ())
    df = pd.DataFrame(rows, columns=["agent_name", "credits_earned", "event_hour"])
    pivot_df = pd.pivot(
        index="event_hour", columns="agent_name", values="credits_earned", data=df
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
            select  * from waypoints_not_scanned_progress 
            union
            select * from jumpgates_scanned_progress
            union 
            select * from mkt_shpyrds_waypoints_scanned_progress
            union
            select * from  mkt_shpyrds_systems_visit_progress
            
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


def ship_overview():
    sql = """select ship_symbol
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

    frames = {
        "FRAME_DRONE": "⛵",
        "FRAME_PROBE": "⛵",
        "FRAME_MINER": "🚤",
        "FRAME_LIGHT_FREIGHTER": "🚤",
        "FRAME_FRIGATE": "🚤",
        "FRAME_HEAVY_FREIGHTER":"⛴️"
    }

    roles = {"COMMAND": "👑", "EXCAVATOR": "⛏️", "HAULER": "🚛", "SATELLITE": "🛰️", "REFINERY":"⚙️"}

    rows = try_execute_select(connection, sql, ())
    response = ""
    if len(rows) > 0:
        response = (
            "| ship | what | waypoint | 📥 | 📦 | behaviour | Locked? | locked_until |\n"
        )
        response += "| --- | ---  --- | --- | --- | --- | --- | --- | --- |\n"
    for row in rows:
        busy_emoji = "✅" if row[8] else "❌"
        frame_emoji = frames.get(row[2], row[2])
        role_emoji = roles.get(row[1], row[1])
        response += f"| {row[0]} | {role_emoji}{frame_emoji} | {row[3]} | {row[4]} | {row[5]} | {row[6]} | {busy_emoji} | {row[7]} | \n"
    return response


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


@app.route("/ships/")
def ships():
    out_str = markdown.markdown(
        ship_str
        % (
            css_blob,
            link_pieces,
            ship_overview(),
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
