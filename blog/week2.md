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

# Seperation of data and behaviour
My initial approach was very object oriented in that, for example with ships, ships had properties, and ships could _do things_, like move, dock, and so on.

However, when shifting to the multi-client approach there became situations where these actions were either hard coded and seperate from the client (bad for interopability), or the ship had be instantiated with a client object. 
This meant that when the DB sdk or the API sdk returned ships, they were instantiated with a DB sdk or an API SDK. A DB SDK couldn't perform actions against the API, and an API SDK had no means for updating the database.

Thus, I made the decision to fully remove even the stubs of the behaviour in the objects and complete the seperation of data and behaviour. 


# Active concerns
* Presently there is a concern that surveys are not being properly transmitted toand consumed by the API. 
* I'm also aware that the cargo transferring doesn't seem to be reflected properly from just caching. There are circumstances when I've seen log entries reporting successful transfer to a ship I know is full, and circumstances where we receive errors from the API because the destination is full - something that the local checking would catch if the cached information is up to date. 