# week3 

There were some initial regressions relating to the week 2 behaviour, since we extracted a lot of the "validate ship is docked" behaviour to the mediator, from lower level stuff.
Ideally the mediator should just do validation, not correction - since that's a divergence in behaviour between the API class and the mediator - if refuel auto docks on one but not the other, it's confusing to potential implementors.

## goals 

we got a small scale starting quest, so very few upfront extractors. Our initial behaviour isn't very efficient, though our logging is pretty interesting. It suggests we're getting between 20 and 30 credits per request from the week 2 script.
I think for this week having a more dynamic behaviour configuration is the way to go.
The initial idea is that instead of a looping behaviour script (e.g. procure), a ship's behaviour thread should be a one and done.
Currently, a management script initialises the ships and they just do their thing forever. There's no mechanism for switching them off, changing their behaviour, or anything like that.
examples - initially we'd like to be able to have the command ship also extract and sell - presently having it survey at the start is inneficient. We should be able to change that behaviour without restarting the script.
examples - eventually we'll start having too many drones and want to be using larger vessels - we should be able to switch off an excavator and switch-in a larger ship without restarting the script.

Thus, our first behaviour orchestrator (conductor) - the conductor will do the following
* Check the list of ships in the DB.
 * In order for a ship to be considered, it must have a behaviour set. It must also not already be locked by another conductor. (we should assume that we will be able to manage multiple ships with multiple conductors, but probably one agent per conductor)
 * if the ship is valid, the behaviour will be prepared, the ship will be locked in the DB, and the behaviour will be started. 
* Check the list of ships currently running.
 * If a ship has completed its current behaviour (it is in the list of ships, but the thread is stopped) check the DB for its assigned instruction and execute.


the way to change a ship's behaviour is to update the assigned behaviour in the DB. Once the ship finishes its current run gracefully, the conductor will pick it up and start it with the new behaviour.
If the current conductor can't handle that behaviour but another one can, then once the lock expires that conductor will pick it up and start it.
QUESTION - how do we specify which haulers are valid targets for ships performing an EXTRACT_AND_TRANSFER behaviour?
ANSWER - that information should be determined at the start of a behaviour's execution. That way if the valid ships change, it'll get picked up next execution