# Week 6

moving into the second half of the 5th reset since I started playing, carrying over goals.
Where are we at? 
* The starting system behaviours are great - ideal for the first few days, with compensation for varying prices for ships.
* We've got rudimentary exploration of the jump gate network, but it's slow and inneficent.
* The mid game hump (moving from small scale ships to medium ships) is proving cumbersome. Ore Hound costs fucked us this time around. 
  * We should throw in commanders as an alternative to ore_hounds, especially once upgraded with more powerful lasers and surveys.
  * We could look at buying command frigates and outfitting them for more powerful mining instead of ore hounds.
  * Ideally compile that behaviour hourly with some heavy computation on market distance.
* Our starting script does have a hiccup in that the satelite isn't immediately and automatically moved to the shipyard
* Our "ping all waypoints" behaviour in the DB doesn't have good handling of uncharted systems - it's not clear if we've got a detailed view of the system or not.

## Goals

* Record 429 counts in the DB, consider queue based throttling 
* ✅ Record whether we've got a detailed view of the waypoint in the DB - add in the DB "find waypoint by" methods
* Alter the remote scan behaviour to do a first ping of markets and shipyards to find out what's available there.
* Record extractions in DB (will require a refactor of the pg_logging client?)
* Record sell orders in DB (will require a refactor)
 * after selling have the behaviour also ping the market for latest prices.
* ✅ Record waypoint chart state in DB (will require a refactor)
 * How to handle systems that _were_ uncharted but are now charted? the upsert doesn't delete the "UNCHARTED" tag. 
 * An event driven thing? or an ETL?
* be selective about which contracts we accept - we should only accept contracts we can fulfill - either because we can buy/sell, or because we can mine/fulfill.
* Satelites should/ could be deployed to shipyards and marketplaces of value.
 * Each shipyard with the lowest_cost available should get a satelite.
 * extra satelites should be deployed to the marketplaces facilitating the current thing.
## Tasks

Currently at each stage the conductor sets a ship's behaviour, with parameters for where and where it should do the thing.
This is great for recurring things, but not great for one-offs, such as "go and survey this system" - which needs to happen maybe once a day at most.

The solution is a "tasks" list - behaviour, parameters, a "value" (priority) and an "assignee". 


## Multi-agent orchestration

Whilst we originally had planned to do a multiboxing solution, this isn't possible due to the discovery that cargo transfer between agents is prohibited.

As such, our system architecture will need to pivot.
We'll have 3 nodes:
* Behaviour set A - Best fully automated set of behaviours
* Behaviour set B - whatever experimental behaviours I'm working on.
* Recon behaviour 

The recon behaviour will be responsible for scaling slowly, whilst focusing primarily on the following
* Surveying asteroid fields where ships from either agent are extracting
* Scanning waypoints & markets
* Ensuring market data is up to date. 



## NEW ASTEROID BEHAVIOUR
FOR EXTRACTORS
* Find asteroids
* Find markets that can accept goods from the asteroids
* Map the asteroid_field to its closest market. 
* Find the best asteorid field, and deploy all extractors there.
* Extract using the most valuable survey (uses galactic average).

FOR TRADERS
* Look at the surveys we actively have from a given asteroid.
* Look at all the market-places that have one or more items in that survey

* Calculate the actual value of this survey at that marketplace
* Calculate the time to travel to that marketplace & number of requests
* Final value is value / travel time.

* REQUIRED ANALYSIS - ARE WE PRODUCING MORE THAN WE CAN EXPORT?
  * if so - the asteroid will run out of surveys.
  * If not - good, the haulers can continue to create surveys.
  * we can produce 10 every 70 seconds
  * a hauler can accept 120, and be filled by an extractor in 840 seconds.
  * two extractors can fill a hauler in 480 seconds. 
  * 10 extractors can fill a hauler 84 seconds - extractors cannot produce surveys
  * Based on the current route duration, we can group extractors with haulers
  * Spare extractors can go extrasolar.
  

* PERSISTING THE TARGET MATERIALS UNTIL NEXT EXECUTION IS IMPORTANT.


new ship_overview view
SELECT s.ship_symbol,
    s.ship_role,
    sfl.frame_symbol,
    sn.waypoint_symbol,
    s.cargo_in_use,
    s.cargo_capacity,
    sb.behaviour_id,
	sb.locked_until,
	date_trunc( 'SECONDS',
	CASE WHEN (now() at time zone 'utc' - s.last_updated) > INTERVAL '00:00'  
    	THEN (now() at time zone 'utc' - s.last_updated) 
    	ELSE interval '00:00'
	END) as LAST_UPDATED
   FROM ship s
     LEFT JOIN ship_behaviours sb ON s.ship_symbol = sb.ship_symbol
     JOIN ship_frame_links sfl ON s.ship_symbol = sfl.ship_symbol
     JOIN ship_nav sn ON s.ship_symbol = sn.ship_symbol
  ORDER BY s.last_updated DESC;