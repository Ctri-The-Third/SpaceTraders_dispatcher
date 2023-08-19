# display commanders & their contract progress

# display ships & behaviours

# display discovered shipyards & market info (if available)
import pandas as pd
import markdown
import psycopg2
from time import sleep
import json
from straders_sdk.utils import try_execute_select

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
%s

# Commanders & contracts

<div markdown = block>%s</div>
<div markdown = block>%s</div>
<div markdown = block>%s</div>


%s
"""

ship_str = """
<title> Ships overview</title>
%s
# Ships & behaviours
%s

%s"""


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
order by ship_symbol
    """

    rows = try_execute_select(connection, sql, ())
    response = ""
    if len(rows) > 0:
        response = "| ship | role/ frame | waypoint | cargo/ | capacity | behaviour | Locked? | locked_until |\n"
        response += "| --- | ---  --- | --- | --- | --- | --- | --- | --- |\n"
    for row in rows:
        busy_emoji = "🔒🚀✅" if row[8] else "🔓😴❌"
        response += f"| {row[0]} | {row[1]}_{row[2][5:]} | {row[3]} | {row[4]} | {row[5]} | {row[6]} | {busy_emoji} | {row[7]} | \n"
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
}, 5000);
</script>
"""


def out_to_file(str, filename):
    str = markdown.markdown(str, extensions=["tables", "md_in_html"])
    file = open(filename, "w+", encoding="utf-8")
    file.write(str)
    file.close()


while True:
    out_to_file(
        agent_str
        % (
            css_blob,
            commander_overview(),
            scan_progress(),
            transaction_summary(),
            javascript_refresh_blob,
        ),
        "overview.md",
    )

    out_to_file(
        ship_str % (css_blob, ship_overview(), javascript_refresh_blob),
        "overview_ships.md",
    )
    sleep(30)
