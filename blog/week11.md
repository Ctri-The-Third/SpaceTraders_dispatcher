# week 11 

restart went off without much difficulty. Some hiccups with the upgrade method locking up the orehound because we couldn't action it (no source on mining lasers). Ore hounds only have 3 mounts and we're going with 1 surveyor 2 mining lasers for the time being. Earwing (another player) has dedicated surveyors and extractors, whereas we're using a combination of mix & match, and using the distributed survey technology. This will make it hard to identify the impact of a survey_II module. Further analysis should be considered.

There's very little time for development this week so I'm just observing.
I've noticed that there are some bottlenecks / points for observation.

* Charts showing prices over time at the starting asteroid
* Decision making about "when it's better to go elsewhere than sell here
* The freighters don't appear to be freighting properly.
* I think our survey game is weak. Earwing's strategy is to concentrate surveyors onto a proportion of her ore hounds and have them be dedicated surveyors. 
she has 80 extractors and 16 surveyors. 
Each extractor has an extraction power of 60. She extracts 60 every 80 seconds * 80 = 4800
She generates 3 surveys every 80 seconds * 16 = 48

Conversely, we have 50 ore hounds, each with survey power 1 and extractor power 50 AND 10 haulers with survey opportunity.
Every 160 seconds we've generated 60 surveys and 2500 extracted material. If we adopt her strategy and aim for 48 surveys per rotation, we'd need 13 ore hounds dedicated to surveying.
The remaining 37 ore hounds would get an extra mining laser and switch up to extracting ~2,220 every 80 seconds, instead of 2500 every 160. 

QUESTIONS FOR STUDY
* Next week (12) - Does switching to dedicated surveying hounds / frigates make sense? (repurposing the starting frigate absolutely does)
* The current production chain of haulers and refiners definitely adds money into the system. Is it breaking even? Is the opportunity cost worth it? (perform queries and chart this)
* Week 13 - does having ore hounds that can't transfer cargo leave the asteroid to sell make sense? (Determine CPR and CPH estimations)
* the recon dispatcher is not behaving correctly and is trying to use the wrong token for some ships.


We had some brainwaves that have informed decision making for our goals.
* Our own ratelimiter 
  * requests are added to a singleton queue
  * the dispatcher (or any API client) can create a singleton consumer thread (Daemon).
  * Because the objects are handled by-ref, we don't need to do anything other than wait for an event to be triggered.
  * Objects added to the queue should be an object with a `request`, an empty `response` that will be populated, and a threading `event` that the consumer will set
  * the queue is a priority quueue.
* Currently our behaviour is updating the market after a transaction. That's computationally expensive, we should only update the market tradegood involved, by using the transaction to update the market tradegood or ship cost.
* ✅ We should validate in the conductor whether or not to assign a task, based on whether or not it's possible. No buying things if we don't have an accessible system for them.
  * Additionally, don't schedule a task until we have enough money for it.
* Seems to be an issue with getting the right surveys out of the DB? put some logging into the DB for extractions, which should include the survey ID.




| stat             | Week 6a    | Week 7a    | week 8a   | Week 9a   | Week 9
| ---              | ---       | ---         | ---       | ---       |
| fleet size       | 14        |38           | isssues   | 38        | 88
| missions complete| 0         |3            | skipped   | 1         | 1
| credits earned   | 4,156,300 |25,163,516   | worse CPH | 7,635,436 | 19,491,643
| requests         | 330,259   |325,241      | in anycase| 139,392   | 336,995
| uptime           | 6d 3h 52m |6d 22h 28m   |           | 6d 23h 25m | 5d 23h 59m
| CPH              | 28,107.79 |151,159.46   |           | 45,863.06 | 135,374
| CPR              | 12.58     |77.36        |           | 54.78     | 57