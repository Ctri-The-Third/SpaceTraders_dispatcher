
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
* Connection limit being hit on the DB - need to figure out 
  * data persistance (mounted volumes)
  * getting the postgrel.conf file into the image
* The manage export behaviour is utilising all the ADVANCED_CIRCUITRY for profit. This behaviour needs reworked to the manage_supply_chain ideal.
  * ✅ Our first effort at a "manage supply chain" has succeeded in boosting the imports of Liquid Nitrogen and Fertiliser, but not the export of Fertiliser.
  * It was unbounded and bankrupted us.
  * ~~We're making it a "force evolution" script that won't be profitable - but will see evolution slowly propagate through the supply chain~~
  * ✅ forcing evolution takes to long, so instead we're just going to make it focus on keeping things unrestricted.
* The manage supply chain has succeeded in making ADVANCED_CIRCUITRY strong, but we still have the issue of the traders scooping it all up for making profit. None of the lower markets have evolved yet, and some of the ships aren't being fully utilised, only kicking in when things get restricted. It might be better, once things are unrestricted, to push IMPORTS from LIMITED up to MODERATE (whilst profitable)
 ## softer ramp test

Experiment to see if we can be more effictive in our ramp, get traders earlier before we get hunners of probes.
* Only probes on shipyards
* no extractors
* 2 siphoners
* 1 extra chain trader
* 1 on missions
* no jump gate

Outcome - seems to be outperforming W, which has stalled on credits. Need to put some condition for expanding the probes further out
