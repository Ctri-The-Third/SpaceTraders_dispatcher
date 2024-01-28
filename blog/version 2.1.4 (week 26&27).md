
# week 26

We finished in 2nd last reset, incredible performance.



## Issues  

* ✅ Week 24/25 (node W) - sent the starting probe to the wrong waypoint, so couldn't buy and more probes. The conductor was having market monitoring override shipyard monitoring tasks.
* ✅ The DB container didn't have ship_mounts table populated because that came from the `reset_db.py` script that we're not using.   Changed to materialized view - fixed node V and C's conductors from failing.
* ❓ Command ship W--1 drifting for chain trades. 
  * Observed again. It's using a cached route so I'ma purge the cache.
* ❓ Performance of UI / DB is attrocious
* the scan thread doesn't continually run
* no way in the UI of observing request utilisation - need a graph
* UI needs some mechanism for indicating when loading is happening / has finished, with a note if a bad statuscode was returned

* ✅ The request consumer terminated, and there is no "restart" Behaviour - it was actually stuck waiting for a request to return, as there wasn't a timeout attach to the send instruction
* ✅ The conductor didn't (And isn't) performing sweeps of the start system to fill in missing market data - forgot to implement this
* ✅ The conductor wasn't ordering jumpgate construction or mission orchestration - forgot to implement this 
* ❓ For some reason timzone info is making its way into the ship cooldown field, causing a type-mismatch. - not sure why, not coming from the DB.
 * Needs fixing in the ship constructor
* ✅ Connection limit being hit on the DB - need to figure out 
  * data persistance (mounted volumes)
  * ❌ getting the postgres.conf file into the image
  * ✅ instead we have an SQL file that alters the settings on init.
* The manage export behaviour is utilising all the ADVANCED_CIRCUITRY for profit. This behaviour needs reworked to the manage_supply_chain ideal.
  * Our first effort at a "manage supply chain" has succeeded in boosting the imports of Liquid Nitrogen and Fertiliser, but not the export of Fertiliser.
  * It was unbounded and bankrupted us.
  * ~~We're making it a "force evolution" script that won't be profitable - but will see evolution slowly propagate through the supply chain~~
  * forcing evolution takes too long, so instead we're just going to make it focus on keeping things unrestricted. a specific "evolve" behaviour will be used to push markets into their extreme states for evolution.
## softer ramp test

Experiment to see if we can be more effictive in our ramp, get traders earlier before we get hunners of probes.
* Only probes on shipyards
* no extractors
* 2 siphoners
* 1 extra chain trader
* 1 on missions
* no jump gate

Outcome - seems to be outperforming W, which has stalled on credits. Need to put some condition for expanding the probes further out


## connection limit

This week we successfully shifted to using a containerised DB, however we ran up against an issue with the number of concurrent conections.  
It seems the postgres.conf file isn't correctly setting the 300 max connections, and we're hitting the 100 limit.

The resulting downtime has meant that the comparrison results aren't reliable, since the clients were often crashing and preventing each other from behaving correctly.  
We can (And should) use connection pools to decrease the amount of time spent making connections in the first place, and reducing the number of connections on the database - however, this re-increases the risk of connection leaks, which previously we'd resolved by having a DB configuration that expected to drop idle connections with little patience, and a client that expects to reconnect connections.

Cause:
* The configuration file we were basing from is not automatically used when intialising the DB 
* we learned the PG_SETTINGS table (which was the key to successfully diagnosing the issue)
* We learned about template databases, but decided to use a simple SQL script to alter system variables during initialization instead.

Impact:
* System instability for several days since once the clients reached a certain size, a failure to open new connections would crash the clients.
* Missed out on the opportunity to compete seriously for the leaderboard
* Sufficient time to experiment on the "manage supply chain" behaviour, and determine where we want the limitations to dwell.
* Decreased total connections to the database
* Longer start times for some reason as the system waits for connections - need to add logging messages.
  * getting and returning a connection to the pool after _every_ query is a huge resource drain - less than connecting to the DB every time, but still a lot.
  * The ships do use connections for fixed periods of time but don't raelly them whilst they're sleeping. What's the prformance drain of an open connction on the DB vs th performance drain of pooling the connections on the client?
  * Definitely going to need to reimpliment ships holding onto connections, but might have them release them whilst doing a sleep operation and thn picking them back up from the pool when neded.


### Further changes - best of both.
* ✅ Try_execute should continue with the connection pool behaviour unlss provided with an optional connection
* ✅ SDKs should yoink a connection from the pool whenever it needs it and hold onto it until instructed to release.
* ✅ SDKs should have a "release" method that returns the connection to the pool
* ✅ connection pool limit should increase to 100

* We implimented a "sleep" method into the SDK that releases connections if sleeping for more than 1 second.
* We readjusted all the behaviours to use this method, and baked releasing into the generic behaviour's "end" method
* So far we're not seeing connections being closed unexpectedly, hanging and deadlocking the system, or reaching the connection limit with 45 ships. I expect if we breach the warp gate and scale to that degre we will have ships waiting for connctions.



# Stats

No stats this week due to several database rebuilds and poor uptime across all builds.
In summary, all agents except C failed.
We will restart concurrent versioning as of week 28
* 27 on node V
* 28/29 on node U
* 23 on node C 