# week 11 

restart went off without much difficulty. Some hiccups with the upgrade method locking up the orehound because we couldn't action it (no source on mining lasers). Ore hounds only have 3 mounts and we're going with 1 surveyor 2 mining lasers for the time being. Earwing (another player) has dedicated surveyors and extractors, whereas we're using a combination of mix & match, and using the distributed survey technology. This will make it hard to identify the impact of a survey_II module. Further analysis should be considered.


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