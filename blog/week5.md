# Week 5 

## Overview

This reset will be a little different, as the developer who handles the reset is on holiday. Thus, our current behaviours will have a whole fortnight to demonstrate themselves.

Additionally, the price of Ore Hounds is *vastly* higher than it was in the previous reset - perhaps because everyone else started buying them asap, perhaps because of developer intervention. 

We will eventually want to scale up our fleet including Ore Hounds, but not from the COSMIC starting system - sending a command ship out to purchase them is a much better idea.

Observation - Pyramid widening, spending less time on the API, the DB has decent coverage, more time being spent on orchestration, and behaviour tuning.
Very satisfying to see a low level fix/change (e.g. surveys) ripple upwards to have positive impacts on behaviour without any change there.


## Goals

* receive_and_fulfill behaviour needs to automatically have contract management if it doesn't already
* compile survey values in the DB
 * Have ships extarcting for money pick the one with the most valuable out
 * Have ships extracting for quest material pick the one with the highest concentration of quest material, and then secondarily the most valuable out in the event of a tie.

* Record contracts in DB 
* Record extractions in DB (will require a refactor)
* Record sell orders in DB (will require a refactor)
 * after selling have the behaviour also ping the market for latest prices.

* Develop A* jump network pathfinding and complete exploration of the network