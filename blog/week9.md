# week 9

It's thursday, and the node U and node V have slowed down substantially from their peaks earlier in the week.
Moreover, we're seeing more failures in the dispatcher and saturation seeming to almost drop.

The conductor that buys ships and the conductor that assigns behaviour are out of alignment, and we ended up with 50 ore hounds instead of 30.
Having switched the spare ore houdns to go explore, we did see a sudden spike in CPH and concurrent ship activity (Before the dispatcher locked up) - suggesting that this drop in CPH is a symptom of oversaturation, not a symptom of the price of ore tanking.

After adding in a 0.1 second sleep to the SDK's recursive retry for requests, saturation dropped off dramatically - so I'm inferring that it was the memory/python failing to handle the recursive depth we were getting to. 
I'm scaling back up to 50 ore hounds for mining, and will keep an eye on the new "seconds per request" average. If this is around 0.33 then the system is handling everything with effectively zero delay. It'll be worth exploring to see if this scales up super high when we're saturated or if it just goes up a little bit.


# Goals
* Build a new bucket class for the session object to prioritise ship actions that enable cooldowns
* ☑️ Fix the recursive behaviour in the utils behaviour which risks deadlocking the dispatcher <---- this one appears to have had biggest impact
* Have the conductor able to identify when it's oversaturated and scale down.
 * ☑️ Build analytics queries for identifying saturation
 * ☑️ Build some sexy charts for CPH, CPR, and saturation.
* ✅ Condense ship overview and create ship detail page
* `Monitor_cheapest_shipyard_price` is calling `ships_view_one` and `ship_change_flight_mode` unecessarily.