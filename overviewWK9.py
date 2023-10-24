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
    sql = """select agent_name, credits_earned as cr, rpm as util, event_hour 
    from agent_credits_per_hour 
    where event_hour >= now() at time zone 'utc' - interval '8 hours'
    order by event_hour desc, agent_name asc
"""
    rows = try_execute_select(connection, sql, ())
    df = pd.DataFrame(rows, columns=["agent_name", "cr", "rpm", "event_hour"])
    pivot_df = pd.pivot(
        index="event_hour",
        columns="agent_name",
        values=["cr", "rpm"],
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
            left join contracts_overview co on ao.agent_symbol = co.agent_symbol and co.expiration >= now() at time zone 'utc'
			where last_updated >= now() at time zone 'utc' - interval '1 day'
            order by 1 asc"""
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

    sql = """with sessions as ( 
select session_id
from logging
where ship_symbol = %s
and event_timestamp >= now() at time zone 'utc' - interval '1 day'
and event_name = 'BEGIN_BEHAVIOUR_SCRIPT'
group by 1 )


SELECT 
  date_trunc('second', event_timestamp) AS event_timestamp_t,
  event_name,
  event_params,
  status_code,
  round(duration_seconds,2) AS request_delay,
  round(EXTRACT(epoch FROM (
     event_timestamp - 
    LAG( event_timestamp) OVER (partition by session_id ORDER BY event_timestamp asc)
  ))::numeric - duration_seconds,2) process_delay
  
FROM logging 
WHERE 
	session_id in (select session_id from sessions)
	and (status_code > 0
	or event_name in ('BEGIN_BEHAVIOUR_SCRIPT','END_BEHAVIOUR_SCRIPT'))

  AND event_timestamp >= NOW() AT TIME ZONE 'utc' - INTERVAL '1 day'
ORDER BY event_timestamp DESC 
limit 100;

"""
    rows = try_execute_select(connection, sql, (ship_id,))

    output_str += """
    
| datetime | request time | other time | event_name | event_params |  
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
    last_ship = ""
    ship_block = """"""
    if len(rows) > 0:
        rows.append(["", "", "", "", "", 0, 0, "", "", ""])
        for row in rows:
            # in a situation where the next row is a different agent - we're done aggregating this agent, and need to add it to the output.
            # the same thing needs to happen if we're accessing a different ship type - we're done aggregating that kind of ship and need to add it to the still-baking agent output

            if last_ship != f"{row[3]}{row[2]}" or row[0] != last_agent:
                if last_ship != "":
                    agent_block = f"{agent_block}* {frame_emoji}{role_emoji}: {shipyard_type_counts[f'{frame_emoji}{role_emoji}']}:  {ship_block} \n"
                last_ship = f"{row[3]}{row[2]}"
                ship_block = ""

            if row[0] != last_agent:
                # only print the header row if this is not the first pass through
                # the header row gets added at the end of the loop
                if last_agent != "":
                    header_block = f"""\n\n### {last_agent}\n
* {last_agent} has {agent_ships} ships, {active_ships} active ({round(active_ships/agent_ships*100,2)}%)\n"""

                    # for key, value in shipyard_type_counts.items():
                    #    header_block += f"* {key}: {value}\n"
                    response += header_block + agent_block + "\n\n"
                    last_ship = ""
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

            ship_block += f'[{busy_emoji}](/ships?id={row[1]} "{row[1]}{frame_emoji}{role_emoji}{cargo_emoji}") '
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
    sql = """refresh materialized view mat_session_stats;
    refresh materialized view mat_session_behaviour_types;"""
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


@app.route("/hourly_stats/<agent_id>")
def hourly_stats(agent_id):
    sql = """with request_stats as (
	select s.agent_name
	, min(event_timestamp) report_start
	, max(event_timestamp) report_end
	, max(event_timestamp) - min(event_timestamp) as report_period 
	, count(*) filter (where status_Code >= 0 ) as requests
	, count(*) filter (where status_code >= 400 and status_Code < 500) as invalid_Requests
	, count(*) filter (where status_Code >= 0 ) / EXTRACT(EPOCH FROM max(event_timestamp) - min(event_timestamp)) as rps
	, avg(l.duration_seconds) filter (where status_code >= 0) as requests_avg_wait
	, max(l.duration_Seconds) filter (where status_code >= 0) as requests_max_wait

	from logging l join ships s on l.ship_symbol = s.ship_symbol
	where s.agent_name = %s
	and event_timestamp >= date_trunc('hour',now() at time zone 'utc') - interval '1 hour'
	group by 1
),
transaction_summary as (
	select s.agent_name
	, sum(total_price) as total_credits_earned
	, min("timestamp") report_start
	, max("timestamp") report_end
	, round(sum(total_price) / EXTRACT(EPOCH FROM max("timestamp") - min("timestamp"))::numeric,2) as cps

	from transactions t 
	join ships s on t.ship_Symbol = s.ship_symbol
	where s.agent_name = %s
	and "timestamp" >= date_trunc('hour',now() at time zone 'utc') - interval '1 hour'
	--and "timestamp" <= date_trunc('hour',now() at time zone 'utc')
	group by 1 
),
cps as (
  select * from request_stats rs join transaction_summary ts on rs.agent_name = ts.agent_name
),
transaction_stats as (
  select agent_name, trade_Symbol, sum(units) as units_sold, sum(total_price) as credits_earned from transactions t join ships s on t.ship_Symbol = s.ship_symbol
  where agent_name = %s
	
  and "timestamp" >= date_trunc('hour',now() at time zone 'utc') - interval '1 hour'
	and type = 'SELL'
	group by 1 ,2
	order by 4 desc
),
extraction_stats as ( 
	select agent_name, trade_Symbol, sum(quantity) from extractions e join ships s on e.ship_Symbol = s.ship_symbol 
	where s.agent_name = %s
	and event_timestamp >= date_trunc('hour',now() at time zone 'utc') - interval '1 hour'
	
 	group by 1, 2
	order by 3 desc
)
select * from transaction_stats

"""

    request_stats_sql = """	select s.agent_name
	, min(event_timestamp) report_start
	, max(event_timestamp) report_end
	, max(event_timestamp) - min(event_timestamp) as report_period 
	, count(*) filter (where status_Code >= 0 ) as requests
	, count(*) filter (where status_code >= 400 and status_Code < 500) as invalid_Requests
	, round((count(*) filter (where status_Code >= 0 ) / EXTRACT(EPOCH FROM max(event_timestamp) - min(event_timestamp)))::numeric,2) as rps
	, round(avg(l.duration_seconds) filter (where status_code >= 0),2) as requests_avg_wait
	, round(max(l.duration_Seconds) filter (where status_code >= 0),2) as requests_max_wait

	from logging l join ships s on l.ship_symbol = s.ship_symbol
	where s.agent_name = %s
	and event_timestamp >= date_trunc('hour',now() at time zone 'utc') - interval '1 hour'
    and event_timestamp <= date_trunc('hour',now() at time zone 'utc')

	group by 1"""
    rows = try_execute_select(connection, request_stats_sql, (agent_id,))
    if not rows:
        return "no data"
    start_time = rows[0][1]
    end_time = rows[0][2]
    duration = rows[0][3]
    requests_valid = rows[0][4]
    requests_total = rows[0][4] + rows[0][5]
    requests_per_sec = rows[0][6]
    requests_avg_wait = rows[0][7]
    requests_max_wait = rows[0][8]
    requests_400s = rows[0][5]

    transaction_stats_sql = """
	select s.agent_name
	, sum(total_price) as total_credits_earned
	, min("timestamp") report_start
	, max("timestamp") report_end
	, round(sum(total_price) / EXTRACT(EPOCH FROM max("timestamp") - min("timestamp"))::numeric,2) as cps

	from transactions t 
	join ships s on t.ship_Symbol = s.ship_symbol
	left join mat_session_behaviour_types msbt on msbt.session_id = t.session_id
	where s.agent_name = %s
    and t."type" = 'SELL'

	and (msbt.behaviour_name is null or msbt.behaviour_name 
		 in ('EXTRACT_AND_TRANSFER_OR_SELL_4','EXTRACT_AND_SELL','EXTRACT_AND_FULFILL_7') )
	and "timestamp" >= date_trunc('hour',now() at time zone 'utc') - interval '1 hour'
	and "timestamp" <= date_trunc('hour',now() at time zone 'utc')
	group by 1 	"""
    rows = try_execute_select(connection, transaction_stats_sql, (agent_id,))
    if not rows:
        return "no data"
    earnings_mining = rows[0][1]
    earnings_mining_ps = rows[0][4]

    transaction_breakdown_sql = """
with hq_systems as (
  select distinct headquarters, w.system_symbol
  from agents a 
  join waypoints w on a.headquarters = w.waypoint_Symbol
),

starting_asteroids as ( 
  select waypoint_Symbol, count(*) from waypoint_traits wt
  where wt.trait_symbol in ('MARKETPLACE','COMMON_METAL_DEPOSITS')
  group by 1 
  having count(*) = 2
  order by 2 desc
)

 select 
   date_trunc('hour',t.timestamp)
   , hs.system_symbol is not null as starting_system
   , sa.waypoint_symbol is not null as starting_asteroid
   , t.trade_symbol in ('IRON','ALUMINUM','COPPER') as processed_good
   , sum(total_price) as earnings
   , sum(t.units) as quantity 
   , round(sum(total_price) / sum(t.units),2) as average_value_per_item
from transactions t 
join mat_session_behaviour_types msbt on t.session_id = msbt.session_id
join ships s on t.ship_Symbol = s.ship_symbol
join waypoints w on t.waypoint_symbol = w.waypoint_symbol
left join hq_systems hs on hs.system_symbol = w.system_symbol
left join starting_asteroids sa on (w.waypoint_symbol = sa.waypoint_symbol)
where t."type" = 'SELL'
and "timestamp" >= date_trunc('hour',now() at time zone 'utc') - interval '1 hour'
and "timestamp" <= date_trunc('hour',now() at time zone 'utc')

and s.agent_name = %s
group by 1,2,3,4
order by 1 desc,3,2,4 """
    rows = try_execute_select(connection, transaction_breakdown_sql, (agent_id,))
    if not rows:
        return "no data - try refreshing?"
    sells_at_asteroid = 0
    sells_in_system = 0
    sells_in_sector = 0
    sells_of_processed_material = 0
    for row in rows:
        if row[2]:
            sells_at_asteroid += row[4]
        elif row[1]:
            sells_in_system += row[4]
        else:
            sells_in_sector += row[4]
        if row[3]:
            sells_of_processed_material += row[4]

    sell_per_trade_symbol_sql = """
select trade_symbol, sum(units), sum(total_price), round(avg(price_per_unit),2)  from transactions t join ships s on t.ship_Symbol = s.ship_symbol
where agent_name = %s
and type = 'SELL'
and t."timestamp" >= date_trunc('hour',now() at time zone 'utc') - interval '1 hour'
group by  1 
order by 1 """
    rows = try_execute_select(connection, sell_per_trade_symbol_sql, (agent_id,))
    if not rows:
        return "no data"
    transaction_lines = []
    total_profits = sum([row[2] for row in rows])
    max_len = max([len(row[0]) for row in rows])
    for row in rows:
        transaction_lines.append(
            (row[0], row[1], row[2], round(row[3], 2), round(row[2] / total_profits, 2))
        )

    out_md = f"""# Stats from {start_time} to {end_time} ({duration})
Requests: {requests_total} ie {requests_per_sec}/s   avg wait: {requests_avg_wait}   max: {requests_max_wait} \n
Actual requests: {requests_valid} ie 2.73/s \n
Wasted requests: {requests_400s} ie 0.0057/s ie one every 2min55s \n
(NOT CAPTURED) Request time avg: 0.27s  min: 0.14s  max: 2.37s \n
(NOT CAPTURED) Rate limiter idle time: 8min59s ie 7.49% \n
--- \n
Credits from extractions: {earnings_mining} ({earnings_mining_ps}/s) \n
Credits from resells: 0 (0.000/s) \n
Credits spent on trade: 0 (0.000/s) \n
Net profit from trade: 0 (0.000/s) \n
Contracts fulfilled: {"new_contracts_fulfilled"} \n
Credits from contracts: {"earnings_contracts"} (0.000/s) \n
Credits spent on contracts: 0 (0.000/s) \n
Credits spent on fuel: {"spendings_fuel"} (51.331/s) \n
Credits spent on ships: {"spendings_ships"} (0.000/s) \n
Net credits gained (without counting ship buys): {"net_credits_without_capex"} ({"net_credits_without_capex_ps"}/s) \n
Net credits per request: {"net_credits_per_request"} \n

Totals: extracts {"requests_extractions"}, amount extracted {"total_extracted"}, credits from sells {"earnings_sells"} \n
### total sells by type
Credits earned at the starting_Asteroid {sells_at_asteroid}  
Credits earned elsewhere in the starting_System {sells_in_system}  
Credits earned outside the starting_system {sells_in_sector}  
Credits from processed material {sells_of_processed_material}  

### extractions per trade symbol (not implemented)

* ALUMINUM_ORE      : exacted 28_643 in 495 actions (avg 57.9, share actions 0.166, share amount 0.167) 
* AMMONIA_ICE       : exacted 29_089 in 501 actions (avg 58.1, share actions 0.168, share amount 0.169)
* COPPER_ORE        : exacted 39_848 in 692 actions (avg 57.6, share actions 0.233, share amount 0.232)
* DIAMONDS          : exacted 2_850 in 50 actions (avg 57.0, share actions 0.017, share amount 0.017)
* ICE_WATER         : exacted 18_433 in 319 actions (avg 57.8, share actions 0.107, share amount 0.107)
* IRON_ORE          : exacted 21_428 in 371 actions (avg 57.8, share actions 0.125, share amount 0.125)
* PRECIOUS_STONES   : exacted 1_868 in 32 actions (avg 58.4, share actions 0.011, share amount 0.011)
* QUARTZ_SAND       : exacted 16_640 in 288 actions (avg 57.8, share actions 0.097, share amount 0.097)
* SILICON_CRYSTALS  : exacted 13_179 in 227 actions (avg 58.1, share actions 0.076, share amount 0.077)\n\n


### earnings per trade symbol
| Trade symbol | units sold | credits earned | avg credits per unit | share of profits |
| --- | --- | --- | --- | --- |

{"".join(str(i) for i in transaction_lines)}

Credits: 360_261_349¢
COMMAND: 1
HYBRID_ORE_HOUND: 0
MANUAL: 1
MINER: 80
PROBE: 0
SURVEYOR: 16
UNCLAIMED_ORE_HOUND: 0
mining_strength:#ships : 0:17,10:1,60:80
survey_strength:#ships : 0:81,1:1,6:16
new_ship_price: 160_000¢
Best listings to buy mounts:
SH(X1-Z40-41827B) I MOUNT_MINING_LASER_II 37231 75352 V:100 MODERATE 19:23:02 in G(Z40) (-10356,9642) from_home:0 unexplored RED\
_STAR  as:1 sh:1 ma:7
No known listing for MOUNT_MINING_LASER_III
QU9-01912B E MOUNT_SURVEYOR_II  18822 38440 V:10 MODERATE 13:48:14 in G(QU9) (-8768,9022) from_home:1705 unqueried RED_STAR  as:\
0 sh:0 ma:0
No known listing for MOUNT_SURVEYOR_III
Survey report: best:632.2 [COP,QUA,AMM,AMM,AMM,IRO] extractions:3 extracted:157 until 22:10:11 available:17 recent_scores:384 ta\
rget:256.2 avg:158.2 over 4122 surveys -- n_extracts: avg:8.1 amount:466.2 over 352 -- avg exhausted score:772.2  8.54% of all surveys --\
 with diamonds: 29/4122 = 0.007 -- new score is positive: 2838 ie 68.85%
"""

    formatted_markdown = markdown.markdown(
        out_md,
        extensions=["tables", "md_in_html"],
    )
    out_str = "%s\n%s\%s" % (css_blob, link_pieces, formatted_markdown)

    return out_str


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4000)
