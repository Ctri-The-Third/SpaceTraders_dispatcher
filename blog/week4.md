# Week 4 

# Week 4 
Once this week is complete, I will have been playing for a month.

# Goals 

I'd like to tighten up the dispatcher from week 3 - it's almost in a good state. Both the dispatcher and the conductor struggle when a DB connection is lost, and we're now at two agents worth of infrastructure.
I'd like some visual display elements that auto refresh - much like metabase gives the refreshable dashboard.

Specifcs:
* Harden dispatcher and conductor to have auto-reconnect and auto-retry behaviour. ☑️
* Dispatcher should launch with args to specify which agent it's executing for. ✅
* Find out why the EXTRACT_AND_SELL script isn't registering that the ship is undocked ✅ (the extract command was doing an undock at too low a level)
* Callibrate conductor stage 3 to get ore hounds and freighters. ☑️
* Have some way of excluding agents from the conductor - for ease of testing. (might be better to have a test DB - time to think about docker containers?) ✅ - (This is easy, just remove the conductor's access to the token for the user in question)
* Credits over time, per agent.
* Ship display, per agent. 
* Get the package compiling and installing. ✅
 
* conductor on nodeA for now
* Node A holds the database - we should move that to rasbee, and host (CTRI-A) on that.
* Node B should become the VPN node (CTRI-B)
* Node U remains the work node (CTRI-U)

# extract and sell_all (2) = 208.5530054644808743, 138.4804063860667634 when counting wasted behaviours
# combined behaviour (3) = 4.5, including wasted behaviours. GARBAGE. sob.
# Let's create EXTRACT_AND_TRANSFER_OR_SELL (4) instead, with parameters being used to define what gets transferred, and what gets sold.

## Extract and Sell or Transfer

Needs the following things
* ✅ Surveys in DB (this is a big one for efficiency) 
  * ✅DB is in local time, ST is in UTC. Need to convert received timestamps to DB Time.  
  * ✅ This behaviour needs to automatically correct for BST/GMT 
* ☑️ Surveys from DB ( currently this is getting a good survey, but not the best survey) 
* Be able to find ships in DB from multiple agents
* Conductor adds behaviour_params for completing CTRI's quests.
* dispatcher needs to get behaviour_params from the database. 