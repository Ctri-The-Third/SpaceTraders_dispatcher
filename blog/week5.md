# Week 5 

## Overview

This reset will be a little different, as the developer who handles the reset is on holiday. Thus, our current behaviours will have a whole fortnight to demonstrate themselves.

Additionally, the price of Ore Hounds is *vastly* higher than it was in the previous reset - perhaps because everyone else started buying them asap, perhaps because of developer intervention. 

We will eventually want to scale up our fleet including Ore Hounds, but not from the COSMIC starting system - sending a command ship out to purchase them is a much better idea.

Observation - Pyramid widening, spending less time on the API, the DB has decent coverage, more time being spent on orchestration, and behaviour tuning.
Very satisfying to see a low level fix/change (e.g. surveys) ripple upwards to have positive impacts on behaviour without any change there.

## Development expereience

At this point most of the structure is in place, and it feels less like I'm solving interesting problems and just tinkering with the game and fleshing it out - in Factorio terms, the main bus is built and I'm just forking off to build the various factories.

Because (unlike factorio) scaling is largely a factor of time and credits, without much need to go back and change behaviours themselves, the game loop experience of continual refactoring is not necessary at this stage of the gameplay.

I think I'll likely see that once I get into the endgame and reach request saturation. I don't currently have signposting / logging for that.
 
## Goals

* ✅ receive_and_fulfill behaviour needs to automatically have contract management if it doesn't already
* ✅ compile survey values in the DB
 * ✅ Have ships extarcting for money pick the one with the most valuable out
 * ✅ Have ships extracting for quest material pick the one with the highest concentration of quest material, and then secondarily the most valuable out in the event of a tie.

* ✅ Record contracts in DB 
* Record cooldowns into DB
* Record extractions in DB (will require a refactor)
* Record sell orders in DB (will require a refactor)
 * after selling have the behaviour also ping the market for latest prices.
* Record waypoint chart state in DB (will require a refactor)
 * How to handle systems that _were_ charted but are now charted? the upsert doesn't delete the "UNCHARTED" tag. 
 * An event driven thing? or an ETL?

* Develop A* jump network pathfinding and complete exploration of the network
* Record 429 counts in the DB, consider queue based throttling 


## Queue based throttling & logging
since pretty much everything is happening in the same application, we can use a queue. 
When the request makes it into the utils function, it puts itself into a global queue, and then checks if the next item is itself. If the next item is itself, it sleeps for 0.3s and executes, otherwise it sleeps for 0.3 and waits.

Currently we have high-level logging.
Logging is a very low-leel thing, and I think if we pass the logging client into the API client as an optional thing (maybe a stub otherwise) then we can have the API client log at a lower level, and the logging client can decide what to do with it.


## Deciding when to go exploring.

There comes a point where it's better to have command ships going out to visit systems on the jump gate network and hitting up shipyards and marketplaces - this initial information can help inform quests. 

This kind of behaviour can be tagged to the command ship - we set it to the asteroid WP and start doing surveys whilst polling systems.

This behaviour should ensure the following
* All systems are in the DB
* The main jump gate network is explored and connected
* All uncharted systems are tagged to be explored
* All marketplace systems are tagged to be explored
* All shipyard systems are tagged to be explored
* Once this is complete, the command ship should depart the main system to explore these systems.

* This behaviour is called "explore_jump_network", and replaces the existing week 4 behaviour.