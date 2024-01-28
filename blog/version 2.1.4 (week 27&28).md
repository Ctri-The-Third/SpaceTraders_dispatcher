# week 28

Database instability continues to be our woe - and we're now back to "idle in transaction" issues causing the database to be locked. 

* We've finally solved this with a mixture of restoring our old settings and properly applying them to the DB, and also implimenting connection pooling.
* Putting "Maintain supply chain" haulers onto the fab_mats and advanced_circuitry markets had a huge impact on the speed of construction.

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
* Further conversation with a dev clarified why evolution doesn't occur immediately. the WEAK, GROWING, and STRONG values on the Activity enum are not reflections of 3 different states, instead much supply they map to a more granular variable that reflects the amount of a good that's consumed per hour. at STRONG this is 2*TV, at WEAK it's 1*TV (with some margin on either side.). RESTRICTED overrides this.  
We were given a hint that MODERATE is enough to make this variable increase - once the variable is high enough (e.g. we're STRONG) we should tip the imports the rest of the way to trigger growth.

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


  
| stat              | Node U (exp) | node V (21) | 
| ---               | ------------ | ----------  |
| total uptime      | 257.29       | 354.16      | 
| total ships       | 84           | 22          | 
| contracts         | 257          | 2           | 
| contract_earnings | 22,025,637   | 0           | 
| trade_earnings    | 148,474,606  | 2,692,372   | 
| total_earnings    | 170,500,243  | 2,692,372   |
| requests          | 1,218,532    | 392,857     |
| average delay     | 9.01         | 0.5         | 
| CPH               | 662,677.30   | 7,602.134   |
| CPR               | 139.922      | 6.85        |
