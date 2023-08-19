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

* ✅Record 429 counts in the DB, consider queue based throttling 
* ✅ Record whether we've got a detailed view of the waypoint in the DB - add in the DB "find waypoint by" methods
* ✅ Alter the remote scan behaviour to do a first ping of markets and shipyards to find out what's available there.
* Record extractions in DB (will require a refactor of the pg_logging client?)
* ✅ Record sell orders in DB (will require a refactor)
 * ✅ after selling have the behaviour also ping the market for latest prices.
* ✅ Record waypoint chart state in DB (will require a refactor)
 * How to handle systems that _were_ uncharted but are now charted? the upsert doesn't delete the "UNCHARTED" tag. 
 * An event driven thing? or an ETL?
* be selective about which contracts we accept - we should only accept contracts we can fulfill - either because we can buy/sell, or because we can mine/fulfill.
* ✅ Satelites should/ could be deployed to shipyards and marketplaces of value.
 * ✅ Each shipyard with the lowest_cost available should get a satelite.
 * extra satelites should be deployed to the marketplaces facilitating the current thing.
* ✅ Currently whenever we want to make a change, we have to reset the dispatcher. I didn't realise how much of an impact it makes, but even a single restart knocks about a thousand credits off the hour's outcome.
 * ✅ Dispatcher needs to stop refreshing threads for ships that aren't returned by the "unlocked" function (already implemented). To phase between them, switch the lock from one to the other, ideally 10 at a time to avoid old_node tanking before new_node is up to speed.
 * ✅ Dispatchers need better names - have ChatGPT come up with 50 possibilities.
 * ✅ What's the best ship / behaviour to expand more of? Is it an excavator, a freighter, or an ore hound? 
   * ✅ How have the behaviours been performing in the last hour?

### Final checklist
* Backup DB
* Reset DB
* Reset clients 


## Where did we end up?

In a really strong place. Getting the transactions into the DB (instead of measuring the start & finish credits of a behaviour) allowed for much easier and more accurate reporting. With this we formed a couple of new analytics queries and our first materialised view (for aggregating session events) - we can look at agent session stats over the last hour, unpartitioned behaviour performance over the last hour, and using the earnings per ship type (vs the minimum price) - decide whether to buy a freighter, extractor, or ore hound. 

Our "Get some extractors to pick out valuable materials and give them to freighters" didn't work out too well - solid CPR but not cost effective compared to the value of the ore hounds (after we found a source of cheaper ones).

Scanning and visiting of jump-gate connected shipyards and markets is going off without a hitch. Need to double check the satelites aren't spamming requests still but that should be easier with fewer ships next week - think we can probably do this better since it locks up the command frigate which could theoretically be doing something else.

We never got passed the messed up quest we accepted last week. Being selective surrounding whether or not we _can_ complete the quest and then whether or not we _should_ complete the quest is vital. might be worth just powering through bad ones on principle.

We discovered that haulers aren't the force multipliers we'd hoped. They provide some CPR yields over just buying and selling, but not enough to justify the ship cost.  
Next week we should experiment with the ideas of basic trading (buy cheap sell high)
Next week we should experiment with the impact of having Ore Hounds going for high-value materials. I suspect this would be great CPR but weaker CPH


# Things I thought about.

## Tasks (one off instructions)

Currently at each stage the conductor sets a ship's behaviour, with parameters for where and where it should do the thing.
This is great for recurring things, but not great for one-offs, such as "go and survey this system" - which needs to happen maybe once a day at most.

One solution is a "tasks" list - behaviour, parameters, a "value" (priority) and an "assignee". 

Another solution is to not set instructions in the conductor every loop, and instead have a seperate process trigger on a regular interval. This latter could theoretically make room for a UI to manage things. Our reporting UI is decent but basic, and being able to drill down on certain views would be cool.


## Priority request queue
Someone on the discord (I forget their name) uses an HTTP proxy that delays requests to the API to handle rate limiting at the hardware level.
This isn't a bad idea, but I'd like to keep everything in the API package if possible. HeapQ and Queuing are in combination a probable solution to this, each instance of the client waiting till its message is at the top of the queue before sending it.

If we add in priority calculations, anything that triggers a cooldown can be bumped to the top of the queue.
Also, we need to be very careful about making sure we don't end up with a jammed queue - some sort of timeout solution is needed.


## Multi-agent orchestration

Whilst we originally had planned to do a multiboxing solution, this isn't possible due to the discovery that cargo transfer between agents is prohibited.

As such, our system architecture will need to pivot.
We'll have 3 nodes:
* Behaviour set A - Best fully automated set of behaviours
* Behaviour set B - whatever experimental behaviours I'm working on.
* Recon behaviour 

The recon behaviour will be responsible for scaling slowly, whilst focusing primarily on the following
* Surveying asteroid fields where ships from either agent are extracting
* Visiting waypoints & markets
* Ensuring market data is up to date. 
