# Week 4 

# Week 4 
Once this week is complete, I will have been playing for a month.

# Goals 

I'd like to tighten up the dispatcher from week 3 - it's almost in a good state. Both the dispatcher and the conductor struggle when a DB connection is lost, and we're now at two agents worth of infrastructure.
I'd like some visual display elements that auto refresh - much like metabase gives the refreshable dashboard.

Specifcs:
* Harden dispatcher and conductor to have auto-reconnect and auto-retry behaviour.
* Dispatcher should launch with args to specify which agent it's executing for.
* Credits over time, per agent.
* Ship display, per agent.
* Get the package compiling and installing.
 