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


## inactive freighters

Noticed that the freighters weren't being given tasks by the conductor, just "receive and fulfill" and being sent to the asteroid. I fixed the default behaviour so it's "find the best CPR for selling these. 

Still have an issue with the conductor not assigning "fulfill" tasks to the relevant ships.



| stat             | Week 6a    | Week 7a    | week 8a   | Week 9a    |  Week 11a  | Week 12a    | Week 13a    | Week 16a   |
| ---              | ---       | ---         | ---       | ---        | ---        | ---         | ---         | ---        |
| fleet size       | 14        |38           | isssues   | 38         | 69         | 69          | 56          | 67         | 
| missions complete| 0         |3            | skipped   | 1          | 1          | 1           | 0           | 0          |
| credits earned   | 4,156,300 |25,163,516   | worse CPH | 7,635,436  | 60,550,875 | 59,525,664  | 102,499,052 | 93,858,132 | 
| requests         | 330,259   |325,241      | in anycase| 139,392    | 861,510    | 663,538     | 441,801     | 687,942    | 
| uptime           | 6d 3h 52m |6d 22h 28m   |           | 6d 23h 25m | 7d 14h 9m  | 6d 9h 1m    | 4d 17h 39m  | 3d 13h 3m  | 
| CPH              | 28,107.79 |151,159.46   |           | 45,863.06  | 332,404.62 | 389,002     | 901,824.62  | 1,103,401.78 |
| CPR              | 12.58     |77.36        |           | 54.78      | 70.28      | 89.71       | 232.00      | 136.43     |
| Average reqest delay |       |             |           |            |            |             |             | 17.48      |

