

# uptime per agent
```sql
WITH sessions AS (
  SELECT session_id, l.ship_symbol, s.agent_name, 
         MIN(event_timestamp) AS min_timestamp, MAX(event_timestamp) AS max_timestamp
  FROM logging l 
  JOIN ships s ON l.ship_symbol = s.ship_symbol 
  WHERE l.ship_symbol != 'GLOBAL'
  GROUP BY session_id, l.ship_symbol, s.agent_name
  ORDER BY s.agent_name, min_timestamp
), downtime AS (
  SELECT agent_name, SUM(next_start_time - max_timestamp) AS total_downtime
  FROM (
    SELECT agent_name,
           LEAD(min_timestamp) OVER (PARTITION BY agent_name ORDER BY min_timestamp) AS next_start_time,
           max_timestamp
    FROM sessions
  ) s
  WHERE next_start_time > max_timestamp
  GROUP BY agent_name
)
SELECT s.agent_name,
       EXTRACT(EPOCH FROM (MAX(max_timestamp) - MIN(min_timestamp))) / 3600 as total_time_hours,
       EXTRACT(EPOCH FROM total_downtime) /3600 as total_downtime_hours  ,
       EXTRACT(EPOCH FROM (MAX(max_timestamp) - MIN(min_timestamp)) - total_downtime) / 3600 as uptime_hours
FROM sessions s 
JOIN downtime d ON s.agent_name = d.agent_name 
GROUP BY 1, total_downtime 
order by 1;


```

```sql 
--ship count
select agent_name, count(*)
from ships 
group by 1;

-- contracts fulfilled
select agent_symbol, count(*) from contracts 
where fulfilled = true
group by 1 ;

--earnings
select agent_name, sum(total_price) 
from transactions t 
join ships s on t.ship_Symbol = s.ship_symbol
where type = 'SELL'
group by 1;

--requests (excluding 429 responses)
select msbt.agent_name, count(*)
from mat_Session_behaviour_types msbt
join logging l on msbt.session_id = l.session_id
 where status_code >= 200 and status_code < 500
and status_code != 429
group by 1 

```