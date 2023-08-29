# week 8

This is the last week in the 2 month block since I started playing Space Traders.
I observe there's generally a burst of enthusiasm around the reset and testing the early stages of my behaviour. Week 7 seems to still be defaulting to buying drones, but I've switched that for week 8 and it seems to better.

The auto populate of the DB has succeeded, and as I type 3815 of the 9116 waypoints on the jumpgate have been scanned. We're not expecting many to be charted at this stage of the game, so pickings will be poor.

We implemented a new conductor for creating and instrumenting accounts for scouting the jumpgate network. This appears to have worked well, there are 108 ships, a quarter are doing surveying at the starting system, the other three quarters are out randomly exploring the network. 

The network isn't fully known yet because of all the charting that needs to happen, so for the time being they're selecting a random gate node that's not been explored yet, and going there. Very inefficient but guaranteed to minimise overlapping with other drones whilst the network is fully explored. Once it is fully explored, they should fall back to circulating all the markets and shipyards we know about.

Finally - we're trying to implement tasks - single instructions for ships to do rather than looping dumb behaviour, which has proven challenging.
I considered some different places for where the decision to execute a task belongs, and decided that ultimately it belongs with the Dispatcher. 

We also added some smart thinking behaviour to our receive_and_fulfill script. If it doesn't have a market/contract to supply, it will look at its cargo, take the largest quantity item (ideally we want it to be just one item per ship tbh) and based on that determine the best CPR to go to. To my delight this behaviour identified a secondary market in the starting system for iron ore and started travelling there. In the morning we'll assess how this has performed. It will be interesting to see what request count for the different trades is. I've hopes that this force muiltiplier effect will prove to a worthwhile investment when prices are this low. 
Also refinery takes 160 seconds per compression. Will need to do some maths on how many extractors are needed per refiner, and if the cost is worth it. My money is "no" for the ore hounds and "yes" for the drones. The failover behaviour of dumping iron ore into haulers rather than the refiner is a smart waterfall approach. 

Requests will either result in high value IRON, mid value ore being hauled away, or low value ore being sold locally.
There's been several sales so far for 5k a pop (yay), but I don't see any IRON being sold, which is a little concerning. Perhaps the trader in question is still filling up with ore. it'll take 29.3 minutes for a light hauler to fill up entirely with IRON, so this actually makes sense.

**Contracts or steady earnings?**
Week 8 behaviour has 1 drone and 1 ore hound, and is therefore in stage 3 going for the contract with command-frigate supporting. I think

Week 7 behaviour has 2 drones and is climbing for an ore hound (after which it should also skip to the contract).

The first behaviour is about 66% complete of the contract, but 70k credits behind the second behaviour. Both behaviours are at aroudn 140k in total earnings since reset, so the question is which will be more profitable by the time the second contract is completed.





**Prioritisaton of refined metal and ore**
Question for the morning - which sell-point got us the most CPH & which the most CPR, between midnight and wake time?
We should focus on CPH. Do the traders CPH outperform the extractors CPH? Probably not. Whichever contributes the most (whether that be ore or refined metal) should be the determinator in which ore we extract from the waypoint.


**Prioritisation of pipeline vs brute force** 
- need to compare the extractor drone CPH / CPR of the buy and sell behaviour vs the buy and transfer deliver, over the course of last night.

**Bug in survey valuation**

I've observed that currently my week 8 behaviour is performing the starting quest, where Aluminium is gathered. It's worth about 126 a unit, so if we're extracting 10 units of that we're getting 1260 credits, just not until pay off.
Meanwhile our best survey is reported as being worth 415/unit - which now I think about it is abnormally high.  When I look at Precious stones, they sell at 88, so unless the survey is giving 100% precious stones, the value should be below 88.  It turned out the average value of the survey wasn't accounting for the number of despoits. I think the determination of which survey was the best, but in terms of seeing that in real term value for my analysis, it was wrong.

Having corrected that, our best survey is getting 59.42 per unit, and I'm much more confident that going for the quest is the correct course of action.

## Goals
**Architecture/ design**
* ✅ Rate limiting scaled up to 3/sec, this is rarely causing issues with 429s. Some, but not many.
* ✅Market Prices needs refactored to be considered of IMPORT/EXPORT/EXCHANGE state.
* survey_average_value needs refactored to divide cost by count of deposits.
* Better analytics for dynamic scaling, hourly events.
* ✅ Implement the recon conductor and dispatcher.


**Behaviour**
* ✅ get ship mounts able to be installed.
* ☑️ get ship upgrades working 
* Add upgrade behaviour into the conductor

**Analytics**
* ✅ get the behaviour_id into the materialised view
* new view we need a ship CPH and CPR - ship_performance
* we need a shipyard_type  CPHPS and CPR 
* we need a behaviour_type CPHPS and CPR
* ✅ session_stats needs a total_cps and a CPHPS