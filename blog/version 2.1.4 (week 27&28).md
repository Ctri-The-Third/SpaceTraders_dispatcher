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


## Ramp up improvements - "Evolve"
Evolution and managing of markets ar actually super seperate, so before we start managing a chain we should evolve it to its best possible state.

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
