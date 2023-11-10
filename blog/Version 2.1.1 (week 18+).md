# version 2.1.1

The SDK is largely functioning again, and last week we achieved some degree of profit and scaling, mired by edge cases dropping our working capital below functional levels for buying fuel and executing trades. 

This week, prices are WAY up, including fuel being prohibitive. This appears to have messed with the "explore one system" behaviour being unable to "go and refuel" between hops properly.

## Step Zero - generate fuel
- ✅ With fuel costs so high, and no market that exports hydrocarbons, we have to start with siphoning and hauling it across the system.
- ✅ Start by moving CMDR to siphon point and having the "SIPHON AND GO SELL".
  - ✅ create Siphon endpoint in API sdk
  - ✅ create Siphons table in DB
  - ✅ expand ship model with "can_siphon" capability.
  - ✅ Question, can we trust "AND GO SELL" to always go to the fuel station? Probably. Worth experimenting with.
- Determine what our CPS from this is. Might be worth getting a siphoner drone to assist before buying a hauler. 
- ❌ once (and only once) supply of fuel at the export is ABUNDANT, begin logging distribution tasks to EXCHANGEs which are not abundant.
  - we can't ensure this and should instead go for when it's HIGH or higher.
  - we've learned that ACTIVITY is a multiplier of production.
  - an abundant supply and heavy exports will trigger market growth to a greater depth.
  - to trigger growth we may have to operate at a slight loss for a while (keep exports SCARCE and supply ABUNDANT)
  - ❗ we did succeed in deploying a task but it bought too much and drained the market, refuel command needs a safety cut-off!
  - with the safety cut off, we can anticipate that this will encourage a strong market depth.
- ✅ once this is complete (and thus fuel is completely topped up), we can log marginal trades that we can afford.
- ✅ For help in tracking this, we've created the 'market_changes' view, which extracts event_params into a more convenient view.
## Step One - Expand the fleet
- ✅ either a hauler (to distribute fuel) or a siphoner (to increase fuel production) 
- Identifing how many trade routes our trade volumes can withstand and scale appropriately. A trade volume of 1 or 10 needs a single visit whenever it's profitable. A trade volume of 100 needs a single hauler, and 1000 probably needs 5+ haulers.

## Step Two - begin evolving markets with intention
Activity seems to be the primary driver of market evolution (and stability), primarily focusing on exports.
An experiment will be to try and buy 1x the trade volume of a specific route every 15 minutes until full, and then 

# Difficulties & Solutions
The problems we faced, the reasoning behidn the solution, and the observed outcomes.

### Fuel costs
Problem: Fuel is absurdly high, and unexpected latency intolerance meant that my initial EXPLORE command didn't execute overnight.



### projects paused mid development
We started on a new event throttler, which is paused for the time being.
We also started trying to do pathfinding for intrasolar, so