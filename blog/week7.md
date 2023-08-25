
# week 7 

## rambling notes
We did a major DB refactor before the maintenance, which has caused lots of issues on the week 6  behaviour on the V node. 
Our scaling was okay, but we messed up a bit - should have purchased an ore hound to start with whilst they were cheap.
Now (Sunday night) ore hounds are up to 400k and we need to go exploring to find a new system to buy them from - set the explorer to go to the systems with the hounds.

ALSO - there are gates in uncharted systems. We need a pathfind behaviour that will periodically refresh those waypoints, and visit the unexplored edges of the jump-gate network. This is critical.

We've achieved handling of buy & sell contracts. presently there are two bottlenecks I'm seeing regularly.
* ✅ restarting threads isn't immediate (which is a flood protection) - this is solved by our theoretical request prioritor
* Things are expensive because we haven't got remote data yet. Both of these are big projects, but the request pooler has a greater risk of messing things up and an enthusiasm stall. It should have its own branch.

We manually moved a satelite after discovering a place we could get cheaper ore hounds (idek how), and that messed up our core conductor expectations. Recon data is a must. It'll sort itself out in stage 4 but for now it's still a bit of a pain.

By Wednesday we've reached saturation at about 56 ships. An hour ago, we had 5.8k requests and 1.1k delays. Note that each delay is an exponential amount up to I think 25 seconds at the moment, with some jitter.
Earlier though, we had an hour with 21.7 CPR and a ratio of 5.7 requests to 6.8 delays. That's unacceptably high, and we need some sort of feedback loop to scale down from high CPH to high CPR until this stops. 

* If we're saturated, we need to look at look at the session stats, switch the earning ships with the lowest CPR and switching them off until the requests ratio is down less than 0.1 delays per request. 
* Current analytics look at ship-type performance, behaviour-performance, and overall session performance
 * We need a more granular assessment of ship-type/ behaviour performance. 
 * I can see that freighters are earning 4153 CPH and 29 CPR for CTRI-U7-
 * But if I look at the behaviour performance, I see the per-ship CPH at 220, or 36.43 for RECEIVE_AND_FULFILL
 * So something is amiss with our analytics, a lack of standardisation. 
 * So I need my mat_session_stats to have the ship_symbol, the shipyard_type, the session_id, the behaviour_id, and the CPR and the pro-rata CPH.
 *  also my mat_session_stats are aggregating incorrectly, seeing ship symbols sharing a sessoin ID? impossible.
 * To decide what to do next, I need better analytics.
 * Optimise what I have before


On a whim (And with discussion with other spacetraders players) I implemented a request throttling system that has now gone into effect. Rather than using a producer/ consumer queue, it uses a very straightforward class that manages a mutex protected pair of timestamps.
When queried, it returns a number of seconds until the queryer can safely execute the request, and increments that time. 
Additionally, there is staggering built in so that VIP requests (those are trigger cooldowns on the ships) can be processed faster. 33% of requests are reserved for VIP requests, and 66% for everything else.
As I watch the system, during spike activity it's still getting rate limits (so something isn't working properly) - with groups of ships all being told to sleep for a _far too similar_ amount of time :( 

We're going to assess.
At the time of writing, the last 4 hours of session performance have seen delays of between 1578, 1704, 2973, and 2788. 
Additionall,y we're seeing a CPH of around 350 on extract_and_transfer at present. If this throttler causes substantial delays, expect to see that be lower (though market prices could also be a factor).
We didn't get to play with refineries or properly fix the freighters, but hopefully we will see fewer delayed requests come the morning.

I've noticed that the VIP requests are at most coming in 0.333 seconds before non VIP ones, which means something is amiss there.



## Goals
**Architecture/ design**
* ☑️ Rate limiting (throttled to 2/sec, issues with 3)
* Market Prices needs refactored to be considered of IMPORT/EXPORT/EXCHANGE state.
* Better analytics for dynamic scaling.


**Behaviour**
* ✅ get ship mounts able to be installed.
* ☑️ get ship upgrades working 
* Add upgrade behaviour into the conductor
* Implement the recon conductor and dispatcher.

## Recon architecture

Conductor should be the one to instantiate agents and assign them behaviours.
We should have a master dispatcher that can execute behaviours for all of those agents.


Difficulty Broadly:
* C Spawn in 🟨
* C Accept quest for upfront payment 🟩 
* C Send to shipyard and buy ships 🟨
* D Be at shipyard 🟨
* C Send commander to be a miner 🟩
* C Send satelites on exploration duty 🟩
* D be on duty 🟩

## Rate limiting architecture

We tried having a slots based system, this didn't work.  
We spoke with a colleague who suggested something fancy involving lambda and a single consumer  
We found the `requests-ratelimiter` python package which enabled a very easy basic implementation that is now live.  
