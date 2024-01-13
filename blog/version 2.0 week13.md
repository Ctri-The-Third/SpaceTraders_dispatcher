# week 13

week 12 was also a minor week. Our focus during that week was instrumenting dedicated surveyors, but we never got around to that, sadly.
That said the week 12 performance was extremely high in terms of CPR after we knocked out all the API calls from the conductor. 

This week I'd like to continue working on the dedicated surveyor behaviour. 
Our questions for study were:
* Next week (12) - Does switching to dedicated surveying hounds / frigates make sense? (repurposing the starting frigate absolutely does)
 * ANSWER: Yes
* The current production chain of haulers and refiners definitely adds money into the system. Is it breaking even? Is the opportunity cost worth it? (perform queries and chart this)
 * ANSWER: not worth it until market crash.
* Week 13 - does having ore hounds that can't transfer cargo leave the asteroid to sell make sense? (Determine CPR and CPH estimations) Does jetisonning garbage cargo make the most sense? 
* the recon dispatcher is not behaving correctly and is trying to use the wrong token for some ships.





## Dedicated Surveyors

We've begun reworking our conductor structure to allow for hourly executions, and daily executions. The daily execution currently is for resetting the uncharted waypoints, to be searched for again.

The hourly behaviour will be for ascribing ship behaviours - relocating fleets etc...

The every-minute will be scaling and buying new ships, and upgrading them.
The new conductor splits ore hounds based on their numerical index.



## Survey collision

We noticed last week that having a single survey be returned for all ships was no ideal - we're actually consuming them significantly faster than we'd expect. This results in a bunch of 409s as ships try and fight over the same survey.

The solution will be assigned surveys to ships. 



end of week stats. 



| stat             | Week 6a    | Week 7a    | week 8a   | Week 9a    |  Week 11a  | Week 12a    |
| ---              | ---       | ---         | ---       | ---        | ---        | ---         |
| fleet size       | 14        |38           | isssues   | 38         | 69         | 69          | 
| missions complete| 0         |3            | skipped   | 1          | 1          | 1           |
| credits earned   | 4,156,300 |25,163,516   | worse CPH | 7,635,436  | 60,550,875 | 59,525,664  |
| requests         | 330,259   |325,241      | in anycase| 139,392    | 861,510    | 663,538     |
| uptime           | 6d 3h 52m |6d 22h 28m   |           | 6d 23h 25m | 7d 14h 9m  | 6d 9h 1m    |
| CPH              | 28,107.79 |151,159.46   |           | 45,863.06  | 332,404.62 | 389,002     |
| CPR              | 12.58     |77.36        |           | 54.78      | 70.28      | 89.71       |

