# week 13

week 12 was also a minor week. Our focus during that week was instrumenting dedicated surveyors, but we never got around to that, sadly.
That said the week 12 performance was extremely high in terms of CPR after we knocked out all the API calls from the conductor. 

This week I'd like to continue working on the dedicated surveyor behaviour. 
Our questions for study were:
* Next week (12) - Does switching to dedicated surveying hounds / frigates make sense? (repurposing the starting frigate absolutely does)
 * ANSWER: Yes
* The current production chain of haulers and refiners definitely adds money into the system. Is it breaking even? Is the opportunity cost worth it? (perform queries and chart this)
 * ANSWER: unknown
* Week 13 - does having ore hounds that can't transfer cargo leave the asteroid to sell make sense? (Determine CPR and CPH estimations)
* the recon dispatcher is not behaving correctly and is trying to use the wrong token for some ships.


## Dedicated Surveyors

We've begun reworking our conductor structure to allow for hourly executions, and daily executions. The daily execution currently is for resetting the uncharted waypoints, to be searched for again.

The hourly behaviour will be for ascribing ship behaviours - relocating fleets etc...

The every-minute will be scaling and buying new ships, and upgrading them.
The new conductor splits ore hounds based on their numerical index.

## Survey collision

We noticed last week that having a single survey be returned for all ships was no ideal - we're actually consuming them significantly faster than we'd expect. This results in a bunch of 409s as ships try and fight over the same survey.

The solution will be assigned surveys to ships. 