# week 28

Database instability continues to be our woe - and we're now back to "idle in transaction" issues causing the database to be locked. 

The first transaction to lock itself was one on node U - ship CTRI--4  
`select total_seconds, expiration from ship_cooldown where ship_symbol = 'CTRI-U--4'`

Intestingly, the thread appears to have moved beyond the database (perhaps because it got a bad response from a timeout) and is now stuck waiting for the request consumer, which has jammed. Attempts to pause it and inspect are failing, which is fascinating.

## ramp up improvements - "Trade best"

Chain trading is pretty good for efficiency, but during the ramp up we really want one ship trading the best possible trade - the commander.

I've created a simple "trade best" behaviour that will look at the best trade available and execute it. It can be optimised by factoring in the distance to the starting location. The commander is set to use this behaviour when it's trading.

## Ramp up improvements - "Manage supply chain"
so far we've not automated the fancy supply chain managment behaviour from last time - but additionally we observed markets evolving whilst restricted. This means that restricted doesn't block evolution, but does slow price changes. Evolving a restricted market is easier whilst they're restricted. Thus, focusing on evolution step by step is the best way, not trading exports UNTIL their imports are evolved. That's unlikely to happen since our other trade routes are going to want to trade the those exports, and we don't have a reservation system.

Through this we've identified that there is a difference between a STRONG market, a GROWING market, and a WEAK market in terms of production rate. 

## Ramp up improvements - "Evolve"
Evolution and managing of markets ar actually super seperate, so before we start managing a chain we should evolve it to its best possible state.

* Exports (Microprocessors, Ship Plating, Clothing, Jewelry) all seem to have evolved naturally to 43 / 15 (3x:(2x + 3)) - which is helping recovery. however imports are not automatically improved by standard trading behaviours.
* My `HYDROCARBON` -> `FUEL` import has gottn stuck at 123:60. This suggests that the maximum import ratio is 2:1 for growth, but I've seen 3:1 in the past. Do I push the corresponding export higher and see if the necessary steps are 2:1, 2:1.5, 3:1.5 ... 180:120? 
  * Waiting was the right call, I see Liquid Hydrogen was able to get to 136:60, so it's definitly possible to push to 180 in one go. Just need to flood the import again.
* Difficulty! Because the local exchanges have TVs of 180, it takes a _while_ to push them into states where they're profitable to inflate their matching imports to ABUNDANT. So far we've seen liquid nitrogent frequently get up to HIGH and bump to 81TV. The exchange price for liquid nitrogen is around 32, and the the optimum sell price is something like 28. As such, I've increased the number of siphoners, since we're definitely extracting less than we need.

* Through this we've learned that a STRONG market generates/consumes 2*TV an hour, which is long enough to let a market slide ABUNDANT to HIGH. This is an opportunity for the task system, but leaves ships idle once the optimal state is achieved. Presently we've been saying "go and enhance the next market" but I think we might want might want to install traders with a singleton trade coordinator that guarantees collision avoidance. That way when finished doing an EVOLVE or MAINTAIN CHAIN they can do the nearest best trade instead, returning if necessary.

## Command and control

We're at the point where we want to be able to make instructions via the UI.

* Must haves
    * Log task for ship
* Set behaviour for ship
* direct move, buy, sell instructions.



## performance

* Node C (22-23)- Didn't do initial exploration and entered a crash loop. to be retired.
* Node V (26-27) - Did initial exploration, but kept instructing the commander to go buy a ship that it couldn't afford. Terminating the conductor for an hour or two should unpick that.
* Node U 
  * Crashed itself buying too many ships, performing high-volume low-marketdepth trades, and keeping the jump gate constructor on whilst ramping.
  * is relocating probes every hour. Why? it shouldn't relocate them at all.