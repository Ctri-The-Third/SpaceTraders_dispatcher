# week 8

This is the last week in the 2 month block since I started playing Space Traders.
I observe there's generally a burst of enthusiasm around the reset and testing the early stages of my behaviour. Week 7 seems to still be defaulting to buying drones, but I've switched that for week 8 and it seems to better.

The auto populate of the DB has succeeded, and as I type 3815 of the 9116 waypoints on the jumpgate have been scanned. We're not expecting many to be charted at this stage of the game, so pickings will be poor.

We implemented a new conductor for creating and instrumenting accounts for scouting the jumpgate network. This appears to have worked well, there are 108 ships, a quarter are doing surveying at the starting system, the other three quarters are out randomly exploring the network. 

The network isn't fully known yet because of all the charting that needs to happen, so for the time being they're selecting a random gate node that's not been explored yet, and going there. Very inefficient but guaranteed to minimise overlapping with other drones whilst the network is fully explored. Once it is fully explored, they should fall back to circulating all the markets and shipyards we know about.

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
