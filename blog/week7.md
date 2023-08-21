
# week 7 

We did a major DB refactor before the maintenance, which has caused lots of issues on the week 6  behaviour on the V node. 
Our scaling was okay, but we messed up a bit - should have purchased an ore hound to start with whilst they were cheap.
Now (Sunday night) ore hounds are up to 400k and we need to go exploring to find a new system to buy them from - set the explorer to go to the systems with the hounds.

ALSO - there are gates in uncharted systems. We need a pathfind behaviour that will periodically refresh those waypoints, and visit the unexplored edges of the jump-gate network. This is critical.

The starting quest will complete in a couple hours, give us a solid 100k. Unless the next quest is for ore, it'll be rejected, but we've not got handling for "can we visit a market to acquire this" behaviour yet.


# Scaling analytics test.


ship_ore_hound = 418590
miing_drone = 88934

for sessions between 01:30 and 09:00

how many times more effective was the oure hound than the mining drone?
That should be our baseline for whether or not to buy a hound or a drone.

note that we are acquiring quest items in this time, we should count those at 135cr per thing extracted?
we don't capture extractions yet, nvm.
