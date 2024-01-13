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


## Motivation.

Minecraft, and Factorio are two games I really enjoy, and both of them have similar "failure state" for my engagement. In minecraft, I die and my inventory items are trapped in a space that's impractical to retrieve. Since there's a real time effort involved in a lot of the items that will be lost, the sense of "oh that's going to take AGES to rebuild from" is immediate and overpowering. 

The same is true in Factorio, though there one has a different option.
If you've built your factory well enough, at the point in which you overreach and lose progress, the factory will be replacing those items for you, with no additional effort required, just time. In those circumstances, the emotional impact is less.

I've noticed it happens in programming, and in other fabrication projects I've been involved in. When I had to rewire a small electronics box to scale it up, my enthusiasm died pretty quickly as soon as I passed the easy-wins in the scaling up process. Same is true when refactoring, once the project is in a broken state due to a major refactor, the risk of crashing as soon as I encounter a stumbling block is extremely high.

### Mitigation

I want this project to last longer - the fact we're on week 3 is already a testament to good management of my own emotions and enthusiasm.  
Despite that, enthusiasm and progress have decreased as the project has gotten bigger. I've been working on it like a pyramid - the base has gotten very wide and there are lots of layers that need expanded before work on the top is possible.

This has decreased the need to refactor over time - the client interfaces make maintenance take longer but everything is neater and I've not tied  this project into a knot that would be overwhelming to face and deal with - my technical debt is relatively low. There are still things that need doing (plenty functions in the mediator are still unabstracted API calls) - but the project is in a good and healthy state, I can continue.

At the moment I'm feeling less enthused but not actively turned off from the project. It feels a little too big to be working on the conductor and dispatcher at the moment, so I'm going to narrow focus. Testing the dispatcher and conductor is challenging with two agents - so I'm going to take my main agent in its Week 2 working state and deploy that into a secondary IP address, and leave it to run itself. 

Then I will focus the dispatcher on working on the test agent, making sure each piece of behaviour works.
I'm tempted to build new behaviours in pytest - doing a complete repeatable e2e test of behaviours without relying on static values would be a better way of testing the mediator client - whilst testing the individual clients is better handled by unit tests.

Building it this way also has the advantage of having a satisfying series of green check-marks appear. I wonder if there's a way to force pytest tests to run in series not parallel so the results of one feed into the next - probably is.


# End of week 3 

My conductor script is doing okay, and my dispatcher too. I've got a raspberry pi setup outside of my house so I can run a production script continually whilst tinkering with my dev scripts without running into issues.  
I'm not feeling super enthused, and think I need more visual feedback - the ships cargo bay status, credits over time, and the physical location of ships would be excellent things to be able to watch in satisfaction.

I have access to all that info inside the DB, so I might spend some time organising the data so that it can visualised.
- a webpage that shows a list of ships (and their cargo capacity), and if possible an image of the starter system.
