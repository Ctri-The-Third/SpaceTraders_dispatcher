# week 16

version 2.1 was delayed so I'm shoring up the codebase and continuing work on the visualiser.
I want to achieve the following:

* Render a given system
* show ship locations / counts of ships at a given location

* Then I want a mechanism by which I can orchestrate new tasks for ships via a UI.


## SSL connection has been closed unexpectedly

This issue perplexed me for a some time. Essentially some of my poorly understood keepalive configuration was causing the connections that I was feeding down into my dispatched ship threads to be closed by the server, which wouldn't be discovered until executing the first command.

The first command was invariably "log beginning event" which meant that my ship logs were never properly associated with the correct ship - which is all keyed off the begin event (this captures events tied to the global ship ID)

I've dunmied out the dispatcher's `get_connection()` method so that's devolved down to the behaviour threads / SDKs to manage now.