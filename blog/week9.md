# week 9

It's thursday, and the node U and node V have slowed down substantially from their peaks earlier in the week.
Moreover, we're seeing more failures in the dispatcher and saturation seeming to almost drop.

The conductor that buys ships and the conductor that assigns behaviour are out of alignment, and we ended up with 50 ore hounds instead of 30.
Having switched the spare ore houdns to go explore, we did see a sudden spike in CPH and concurrent ship activity (Before the dispatcher locked up) - suggesting that this drop in CPH is a symptom of oversaturation, not a symptom of the price of ore tanking.

After adding in a 0.1 second sleep to the SDK's recursive retry for requests, saturation dropped off dramatically - so I'm inferring that it was the memory/python failing to handle the recursive depth we were getting to. 
I'm scaling back up to 50 ore hounds for mining, and will keep an eye on the new "seconds per request" average. If this is around 0.33 then the system is handling everything with effectively zero delay. It'll be worth exploring to see if this scales up super high when we're saturated or if it just goes up a little bit.


# week 10 

Because we didn't ge the week 8 behaviour to run permanently without assistance, I'm rolling the 9 and 10 into a single release for the purposes of charting.


With only 45 ships but still getting the kind of delays we were seeing in the late game last week, it's clear there's something wrong. 

I've identified that the issue appears to be overload on the database itself. One of the spacetraders devs shared the [https://www.postgresql.org/docs/current/pgstatstatements.html](pg_stat_statements) extension, which I've installed and enabled. 

It's apparent that most of the expense comes from updating the ships in the DB, so I'm going to add some "dirty" flags to indicate when we should/should not update any of the objects in the DB. We already handle most of the updating via the ships object and the object's "update" method, which is incredibly fortunate and reduces the dev footprint something fierce.

The above change resulted in significant improvement in query usage, huzzah!
We have two active issues that are toppling the system. as of yesterday "urllib3.connectionpool  Connection pool is full, discarding connection: api.spacetraders.io" - which I think might be because we've increased the bucket size for the session object? going to try find and increase the connection pool to match.

The second is the soft locking that has yet to be adequitely explained, and requires the entire dispatcher to by hard-killed before it can be started up again.
I observed the soft-lock occurred when we restarted the U dispatcher - or more likely, when we reset all the ships_locked values. I'm going to assume it's a DB locking issue and see if tinkering with the connection object is the way forwards there.

Update on the soft-locking! I've implemented additional "how long did this take" tracking in the overview page. It works based on the `lag` sql function so counts sleeps as execution time. This is understandable and not hugely a big deal, but it did highlight several log entries where the execution time was over an hour!!
This prompted further investigation of PGAdmin and I foudn several transactions stuck in the "idle in transaction" state, and this was locking several connections (connections which are shared) from updating the agent table.
The query that got stuck in transaction is the standard "uptrade market tradegood" query which is currently the most expensive impact on the DB.

solutions: 
* StackOverflow suggests this is a problem with transaction management that needs fixed at the source in my code. Since it's an intermittent issue possibly caused by a crash / network hiccup, that's going to be super challenging to fix.
  - it turns out I wasn't doing cursor.close(), or `with connection.cursor() as cursor:` - which was resulting in a lot of transactions / DB sessions being left open and filling things up. That simple change has solved a lot of bottleneck there. I also switched raspberry pis around and put the DB on one with more ram.
* I can "prevent the worst from happening" but setting `idle_in_transaction_session_timeout` - which I'll set to 60 seconds. This will result in the DB getting locked for at most 60 seconds. I won't have an easy way of identifying when this happens though. 
  - I haven't seen this be necessary since the first issue was solved, but it was keeping things moving back then so I'm going to keep it. Don't think it's strictly necessary tho.
* Add client side comparrison of market data and only upload to the DB when there's an actual change in a given market good. each tradegood will probably need a "dirty" flag.

# Goals
* Build a new bucket class for the session object to prioritise ship actions that enable cooldowns
* remove the "ships_view_one" from the initialisation of behaviours, as it's impacting the dispatcher by having it depend on the request bucket
* ✅ add upgrading of ore hounds
 * Update the "extract until full" behaviour to not extract if more than half of the yield would be wasted  
 * ✅ add mounts into the database
* add upgrading of surveying freighters to surveyor IIs
* ☑️ Fix the recursive behaviour in the utils behaviour which risks deadlocking the dispatcher <---- this one appears to have had biggest impact
* Have the conductor able to identify when it's oversaturated and scale down.
 * ☑️ Build analytics queries for identifying saturation
 * ☑️ Build some sexy charts for CPH, CPR, and saturation.
* ✅ Condense ship overview and create ship detail page

* `Monitor_cheapest_shipyard_price` is calling `ships_view_one` and `ship_change_flight_mode` unecessarily.
* `conductor week10` is having to query ships for their mounts, due to caching. 

| stat             | Week 6a    | Week 7a    | week 8a     |Week 8   | Week 9
| ---              | ---       | ---         |  ---        | ---       |
| fleet size       | 14        |38           | 60          | 86        | 88
| missions complete| 0         |3            | 1           | 1         | 1
| credits earned   | 4,156,300 |25,163,516   | 15,506,754  | 7,635,436 | 19,491,643
| requests         | 330,259   |325,241      | 296,051     | 139,392   | 336,995
| uptime           | 6d 3h 52m |6d 22h 28m   | 3d 21h 10m  | 6d 22h 29 | 5d 23h 59m
| CPH              | 28,107.79 |151,159.46   | 166,520.36  | 45,863.06 | 135,374
| CPR              | 12.58     |77.36        | 52.38       | 54.78     | 57