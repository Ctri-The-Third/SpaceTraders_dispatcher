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
* ✅ Alter the remote scan behaviour to do a first ping of markets and shipyards to find out what's available there.
* Record extractions in DB (will require a refactor of the pg_logging client?)
* ✅ Record sell orders in DB (will require a refactor)
 * ✅ after selling have the behaviour also ping the market for latest prices.
* ✅ Record waypoint chart state in DB (will require a refactor)
 * How to handle systems that _were_ uncharted but are now charted? the upsert doesn't delete the "UNCHARTED" tag. 
 * An event driven thing? or an ETL?
* be selective about which contracts we accept - we should only accept contracts we can fulfill - either because we can buy/sell, or because we can mine/fulfill.
* ☑️Satelites should/ could be deployed to shipyards and marketplaces of value.
 * ✅ Each shipyard with the lowest_cost available should get a satelite.
 * extra satelites should be deployed to the marketplaces facilitating the current thing.
* ✅ Currently whenever we want to make a change, we have to reset the dispatcher. I didn't realise how much of an impact it makes, but even a single restart knocks about a thousand credits off the hour's outcome.
 * ✅ Dispatcher needs to stop refreshing threads for ships that aren't returned by the "unlocked" function (already implemented). To phase between them, switch the lock from one to the other, ideally 10 at a time to avoid old_node tanking before new_node is up to speed.
 * ✅ Dispatchers need better names - have ChatGPT come up with 50 possibilities.
 * What's the best ship / behaviour to expand more of? Is it an excavator, a freighter, or an ore hound? 
   * How have the behaviours been performing in the last hour?
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
