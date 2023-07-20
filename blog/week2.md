# week 2 

### Summary of week 1 
Last week we figured out the following:
* Moving
* Extracting
* Selling
* Delivering to contracts.

We used this in a loop of scaling up extractors which sold undesired resources and delivered quest cargo to the deliverable waypoint.  
Later in the week we noticed that the extractors have speed 2, but the command ship has speed 30.  

So in addition, we learned:
* Transferring cargo
* Gathering surveys
* using surveys (not sure this is working)

we split behaviour between freighters (just the command ship), and the extractors - with extractors trying to dump deliverables to the command ship and selling all the excess, the command ship performing surveys until full then delivering (And selling any excess leftover, which will account for when the contract is complete)

We overcomplicated our "Responses" object, initially we had lots of different responses for each different endpoint, but did a large refactor to stop that.
Instead by the end of the week we had a SpaceTradersResponse class that handled all the responses, with most API calls returning either the desired list of objects, or the response. The response also has a convenient boolean expression that lets us simply check `if response:` to see if the request was a success.

# Databasing
The for week two was to have a postgres database set up to act as persistant storage that could (theoretically) be accessed by seperate clients running in a distributed fashion.

We ran into the problem of "do one thing, and do it well" and "seperate the data from the behaviour" which has been the focus of refactoring this week (and will probably continue into subsequent weeks).
The first problem was that our API SDK shouldn't be responsible for interacting with the database - users of this package should be able to interact with the API without having a dependency on Postgres. The solution was (unfortunately) three new classes.
* The interface class which specifies what methods are available.
* an API class which implements that 
* a mediator class which also implements that. The mediator class handles all the in-memory caching, and routes queries to its own instance of the API class if it can't handle that.
* We've begun early work on the postgres client. The mediator class checks in-memory information, then the db, then finally the API if there are no hits, and is responsible for triggering the appropriate "update" methods on the postgres client and db client

The advice was received was to have the mediator client seperate from the caching client, but we made the decision to bake those two together for now, in the interests of maintaining progress.

We succeeded in a creating a behaviour script that has a given ship check every waypoint in the system with either shipyard or marketplace traits, and trigger the update methods. So far the basic shipyard information and detailed marketplace information are being restored - the storage of ship information is a very complex matter.

We've updated the `procure_quest` script with auto-scaling for freighters as well, as we found we had too many extractors for the command ship to handle.  The freighters will also be able to do surveying, which will increase the efficiency in the long run.

# Active concerns
* Presently there is a concern that surveys are not being properly transmitted toand consumed by the API. 
* 