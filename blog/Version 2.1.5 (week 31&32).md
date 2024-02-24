# Week 31/32

We can now set behaviours individually, and Space Admiral has sorted some more of interstellar trading.

Unfortunately, for reasons as yet unclear, the Node-U behaviour didn't properly start executing TRADE_BEST_INTRASOLAR for the command ship.
With Justin back and active (and already in first place), the focus is going to be largely on enhancing reliability and performance, not new strategies.

Node-V isn't doing anything at all, when I restarted the dispatcher I got a bunch of errors from it attempting to map to a system it's not in?  
Turns out we need to purge the cache between resets. Maybe the clint should do that if the system's dates don't match up with the service?


## performance

| stat              | Node U (exp) | node V (26-27) | node C (27-28) |  
| ---               | ------------ | -------------  | -------------- | 
| total uptime      | 
| total ships       | 
| contracts         | 
| contract_earnings | 
| trade_earnings    |
| total_earnings    | 
| requests          | 
| average delay     | 
| CPH               | 
| CPR               |


## Stagnation

It's really feeling like we've not made any progress for a while.  
With that in mind, it might be good to draw a line under this client, fix some of the structural issues with the SDK, tag it v2.0 and start again.



### So what worked?

* The "trade best" doesn't compete with Justin but it's very good in principle. 
* The "Chain Trade" technology worked very well.
* Having generic behaviour methods for travel, refuel, buy, sell, extract_till_full 
* The "contracts" and both "management" behviours worked well but sometimes had downtime.
* straightforward "mine and go sell" works
* The request throttler and ship-specific priorities 
* The pathfinder did great except for assumption that it always had the latest data.
* Putting the DB and and the UI in containers was great for resets.
* The UI being publicly hosted was great

### What didn't work?

* Weekly reset and caching issues were a pain. If we want an "always in memory" approach, the SDK will need to be more robust about managing when market data is old.  
* The UI being a seperate process meant exposing logs to the player and getting feedback from actions was a right pain.  
* The UI being an "all in one window" ended up being harder to work with than I'd hoped. 
* Mistakes made in the SDK were hard to fix (seperate tables for markets etc...)
* A limitation of the old design was that it really was one-ship per client, controlled by the DB, with the potential of split behaviour.


### What should our new client do?

* We should try to be as stateless as possible to allow for quick "off then on" again. 
* Haulers should have three priorities - strengthen markets, trade ABUNDANT/ HIGH, and then haul mining goods & fuel.
* Have a unified system for picking what to do next, and a thread-safe mechanism for avoiding collisions - ships should be aware of each others actions, states, and behaviour.
* Have a UI that works on mobile. 
* Have a UI that lets you take direct control of a ship, and activate any of our "blocks" of code (Travel, refuel, extract, buy, sell, build etc...)
* Have a UI that shows market changes over time.
* Have a UI that renders a production chain.
* Allow multi-token operation - our public UI should be for any player to control their ship.
* work when the user isn't on the browser
* Visualise ship movements / distance in real time.
* Have a comparison mode for previous resets.
#### Archive the current client 

* Get the dispatcher container up to speed, it should have a sigterm intercept for graceful shutdowns.
  * the sigterm signal is being captured
  * the compose file is written
  * [the DB container is out of date]
  * The UI container is able to connect to the DB
  * the dispatcher is able to connect to the DB
* Have a cron job that spins up a new container every 3 hours


#### Development milestone 1

* Token management from the UI.
* Logs fedback to the user (websocket?)
* execute move, buy, sell blocks to ships from the UI.
