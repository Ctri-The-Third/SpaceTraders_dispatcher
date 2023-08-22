
# week 7 

We did a major DB refactor before the maintenance, which has caused lots of issues on the week 6  behaviour on the V node. 
Our scaling was okay, but we messed up a bit - should have purchased an ore hound to start with whilst they were cheap.
Now (Sunday night) ore hounds are up to 400k and we need to go exploring to find a new system to buy them from - set the explorer to go to the systems with the hounds.

ALSO - there are gates in uncharted systems. We need a pathfind behaviour that will periodically refresh those waypoints, and visit the unexplored edges of the jump-gate network. This is critical.

We've achieved handling of buy & sell contracts. presently there are two bottlenecks I'm seeing regularly.
* restarting threads isn't immediate (which is a flood protection) - this is solved by our theoretical request prioritor
* Things are expensive because we haven't got remote data yet. Both of these are big projects, but the request pooler has a greater risk of messing things up and an enthusiasm stall. It should have its own branch.

We manually moved a satelite after discovering a place we could get cheaper ore hounds (idek how), and that messed up our core conductor expectations. Recon data is a must. It'll sort itself out in stage 4 but for now it's still a bit of a pain.


## Goals
* get ship mounts able to be installed.
* Implement the recon conductor and dispatcher.
* Market Prices needs refactored to be considered of IMPORT/EXPORT/EXCHANGE state.
# Scaling analytics test.


ship_ore_hound = 418590
miing_drone = 88934

Q: for sessions between 01:30 and 09:00

how many times more effective was the oure hound than the mining drone?
That should be our baseline for whether or not to buy a hound or a drone.

note that we are acquiring quest items in this time, we should count those at 135cr per thing extracted?
we don't capture extractions yet, nvm.

A: about 2x effective.

Some observations - others suggested that I should work on getting upgraded mounts as part of my flow. Given the current cost of the ore hound, doubling their effectiveness is a good idea. 
We'll reach the point soon where an upraded commander is the better option over an ore hound.

# Recon architecture

Conductor should be the one to instantiate agents and assign them behaviours.
We should have a master dispatcher that can execute behaviours for all of those agents.


Broadly:
* C Spawn in 🟨
* C Accept quest for upfront payment 🟩 
* C Send to shipyard and buy ships 🟨
* D Be at shipyard 🟨
* C Send commander to be a miner 🟩
* C Send satelites on exploration duty 🟩
* D be on duty 🟩

