# display commanders & their contract progress

# display ships & behaviours

# display discovered shipyards & market info (if available)

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

cursor = connection.cursor()

mk_str = """
%s

# Commanders & contracts

<div markdown = block>%s</div>
<div markdown = block>%s</div>

# Ships & behaviours
%s

%s
"""


def scan_progress():
    sql = """select * from  mkt_shpyrds_systems_visit_progress
            union 
            select  * from waypoints_not_scanned_progress """
    rows = try_execute_select(connection, sql, ())
    output = """| Search | Total | Scanned | Progress |
                | ------ | ----- | ------- | -------- |"""
    for row in rows:
        output += f"\n| {row[0]} | {row[1]} | {row[2]} | {row[3]} |"

    return output


def commander_overview():
    sql = "select * from agent_overview"
    cursor.execute(sql)
    rows = cursor.fetchall()
    response = ""
    if len(rows) > 0:
        response = "| Agent | Credits | faction | ships | last_updated |\n"
        response += "| --- | --- | --- | --- | --- |\n"
    for row in rows:
        response += f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} |\n"
    return response


def ship_overview():
    sql = """select ship_symbol
, ship_role
, frame_symbol
, waypoint_symbol
, cargo_in_use
, cargo_capacity
, behaviour_id
, locked_until from ship_overview
where locked_until > now() at time zone 'utc'
order by ship_symbol
    """

    rows = try_execute_select(connection, sql, ())
    response = ""
    if len(rows) > 0:
        response = "| ship | role/ frame | waypoint | cargo/ | capacity | behaviour | locked_until |\n"
        response += "| --- | ---  --- | --- | --- | --- | --- | --- |\n"
    for row in rows:
        response += f"| {row[0]} | {row[1]}_{row[2][5:]} | {row[3]} | {row[4]} | {row[5]} | {row[6]} | {row[7]} | \n"
    return response


css_blob = """
<style>
body {
font-family: "Lucida Console", Courier, monospace;
background-color:#333;
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

while True:
    out_str = mk_str % (
        css_blob,
        commander_overview(),
        scan_progress(),
        ship_overview(),
        javascript_refresh_blob,
    )
    out_str = markdown.markdown(out_str, extensions=["tables", "md_in_html"])
    file = open("overview.md", "w+")
    file.write(out_str)
    file.close()
    sleep(30)
