# Week 6

moving into the second half of the 5th reset since I started playing, carrying over goals.
Where are we at? 
* The starting system behaviours are great - ideal for the first few days, with compensation for varying prices for ships.
* We've got rudimentary exploration of the jump gate network, but it's slow and inneficent.

But
* Our starting script does have a hiccup in that the satelite isn't immediately and automatically moved to the shipyard
* Our "ping all waypoints" behaviour in the DB doesn't have good handling of uncharted systems - it's not clear if we've got a detailed view of the system or not.

## Goals

* Record 429 counts in the DB, consider queue based throttling 
* Record whether we've got a detailed view of the waypoint in the DB - add in the DB "find waypoint by" methods
* Record extractions in DB (will require a refactor)
* Record sell orders in DB (will require a refactor)
 * after selling have the behaviour also ping the market for latest prices.
* Record waypoint chart state in DB (will require a refactor)
 * How to handle systems that _were_ uncharted but are now charted? the upsert doesn't delete the "UNCHARTED" tag. 
 * An event driven thing? or an ETL?

## Tasks

Currently at each stage the conductor sets a ship's behaviour, with parameters for where and where it should do the thing.
This is great for recurring things, but not great for one-offs, such as "go and survey this system" - which needs to happen maybe once a day at most.

The solution is a "tasks" list - behaviour, parameters, a "value" (priority) and an "assignee". 


## Multi-agent orchestration

during the early stage of the game, we have an abundance of spare request capacity and insufficient ships.
we need 429 counts for this but ideally:

* Look at request utilisation by the primary agent
* Look at the 429 counts across the cluster.

Based on the number of 429s vs utilisation, we can decide whether or not to spin up a new agent.
the new Commander can then be instructed to either go and survey/mine and transfer to the primary agent, or to go and explore the jump gate network. 
These supporting behaviours need to be _extremely light_ on requests to avoid starving the primary agent.

As the primary agent scales up and gains greater capability, we can scale down the supporting agents.
Ideally by the time the primary agent is at the point of being request limited, we've got a jump gate network that's been explored.