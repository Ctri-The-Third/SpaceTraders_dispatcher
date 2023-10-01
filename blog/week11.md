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
* ✅ Currently our behaviour is updating the market after a transaction. That's computationally expensive, we should only update the market tradegood involved, by using the transaction to update the market tradegood or ship cost.
* ✅ We should validate in the conductor whether or not to assign a task, based on whether or not it's possible. No buying things if we don't have an accessible system for them.
  * Additionally, don't schedule a task until we have enough money for it.
* Seems to be an issue with getting the right surveys out of the DB? put some logging into the DB for extractions, which should include the survey ID.
  * We are now more clearly exhausting surveys - however we're still seeing a lot of 409s from using exhausted ones. I believe this is because of the queueing for extraction that's occurring. 

I did a bunch of maths and I want to switch to Earwing's dedicated model of having surveyors and extractors. I believe we can accomplish this with the existing "can_survey" and "can_extract" behaviours, combined with a modified "upgrade to spec" that enables the de-quipping of surveyor modules.
The golden ratio appears to be 6.667 repeating extractors per surveyor - assuming 60 mining strength ore hound and 3 survey strength surveyor. 

at 240k credits, ore hounds and command frigates are equal cost per mount. I think our early gameplay behaviour should be
* Expand to 48 ships, with 6 of those being ore hounds dedicated to surveying.
* Buy 6 command ships, outfitting them with surveyors and switch the orehounds over.  


| stat             | Week 6a    | Week 7a    | week 8a   | Week 9a    |  Week 11a  | Week 12 |
| ---              | ---       | ---         | ---       | ---        | ---        | ---
| fleet size       | 14        |38           | isssues   | 38         | 69         | 69
| missions complete| 0         |3            | skipped   | 1          | 1          | 1
| credits earned   | 4,156,300 |25,163,516   | worse CPH | 7,635,436  | 60,550,875 | 53,803,883
| requests         | 330,259   |325,241      | in anycase| 139,392    | 861,510    | 644,279
| uptime           | 6d 3h 52m |6d 22h 28m   |           | 6d 23h 25m | 7d 14h 9m  | 160.705604364166
| CPH              | 28,107.79 |151,159.46   |           | 45,863.06  | 332,404.62 | 334,797.80
| CPR              | 12.58     |77.36        |           | 54.78      | 70.28      | 83.51