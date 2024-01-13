# week 28

Database instability continues to be our woe - and we're now back to "idle in transaction" issues causing the database to be locked. 

The first transaction to lock itself was one on node U - ship CTRI--4  
`select total_seconds, expiration from ship_cooldown where ship_symbol = 'CTRI-U--4'`

Intestingly, the thread appears to have moved beyond the database (perhaps because it got a bad response from a timeout) and is now stuck waiting for the request consumer, which has jammed. Attempts to pause it and inspect are failing, which is fascinating.

## ramp up improvements - "Trade best"

Chain trading is pretty good for efficiency, but during the ramp up we really want one ship trading the best possible trade - the commander.

I've created a simple "trade best" behaviour that will look at the best trade available and execute it. It can be optimised by factoring in the distance to the starting location. The commander is set to use this behaviour when it's trading.

:

## Command and control

We're at the point where we want to be able to make instructions via the UI.

* Must haves
    * Log task for ship
* Set behaviour for ship
* direct move, buy, sell instructions.