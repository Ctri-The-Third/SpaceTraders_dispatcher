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
  - ❌ with the safety cut off, we can anticipate that this will encourage a strong market depth.
- ✅ once this is complete (and thus fuel is completely topped up), we can log marginal trades that we can afford.
- ✅ For help in tracking this, we've created the 'market_changes' view, which extracts event_params into a more convenient view.
## Step One - Expand the fleet
- ✅ either a hauler (to distribute fuel) or a siphoner (to increase fuel production) 
- ✅ Identifing how many trade routes our trade volumes can withstand and scale appropriately. A trade volume of 1 or 10 needs a single visit whenever it's profitable. A trade volume of 100 needs a single hauler, and 1000 probably needs 5+ haulers.
  - ✅ with 4 haulers, we've exhausted continual trades from 100+ trade routes, and were getting negative values from shallow trades.
  - ✅ We've added a minimum profit _percentage_ to trade routes which are shallow. This will decrease the likelihood of tipping into negative trades.
  - ✅ deep trades have run dry, but shallow trades remain an option - going to run things overnight and see how they behave.

## Step Two - Filling the idle time
- ✅ Begin building the pyramid of production. Start with the earliest bits of the production chain.
  - ✅ extractors' requests should be on a much lower priority than haulers' requests. (-2, e.g. 5 vs 3)
  - ✅ additionally, cooldown and move requests should be a higher priority than others. (+1 e.g. 4 for extractors and 2 for haulers)
  - we should use the dripfeed technology to evolve the simplest metal EXPORTS
    - having conversed with the developers, it seems that before an EXPORT can be evolved, the IMPORTs must be. Therefore, our focus should be on expanding the number of concurrent extractors, and their material focuses. 
  - unless we're trying to force a growth cycle, we should just use the existing ship task solution and keep all markets at their optimal feeding level, and have haulers default behaviour be extractor related.
- I did an analysis of the haulers doing steady trades. It seems like of the 14 active hours in my experiment, only 2.5 hours were used performing trades. So, I need to programatically identify this, and set up extractor/ siphoning efforts to stimulate the production chain.
- ✅ If I want to run the extractors alongside the more profitable trading behaviours, I will need to complete the priorities system in request handling.
- In order to support market evolution and understanding, I'm going to switch all trading behaviours off and buy a tonne of extractors.  


## Step Three - begin evolving markets with intention
* we've observed some market evolutions but these occur in extreme (And usually unprofitable) market conditions, so once markets enter into these situations we rarely go back and check.
- ✅ Deploy satellites to each planet (to monitor all adjacent markets) with a 15 minute sentinel ping.
- create a behaviour that holds IMPORT markets in the ABUNDANT state, and EXPORT markets in the SCARCE state. This can be a less profit restricted version of the existing buy and sell behaviour, that uses drip-feeding to avoid massive losses. 
- QUESTIONS TO BE ANSWERED BY SATELLITES 
  - ✅ does the price change at a faster / slower rate if the matching import/export is abundant or scarce (this would suggest there is a cached supply and it's being consumed) (no, price changes are predictable)
  - ✅ how much the price change in any given supply state? is it a percentage or a fixed rate (does it change more when it's in extreme states?) tradevolume 10, the difference from baseline halfs every 3.5 hours.
  - ✅ does the price change at a faster or slower rate when the trade_volumes are higher (expect faster), yes, much faster in low volumes. 
  - ✅ does the price change faster when the market is GROWING or STRONG?  no it does not
- STRATEGY 
  - ✅  when buying or selling to a tradevolume 10, use dripfeed strategy. Our quarterly tasks should specifically target those at peak prices.
  - ❌ the import markets tend to be higher depth than the export markets, so if going 1->10 or 10-> 100 etc... we should focus on the export prices over the import prices (whilst maintaining a profit protection mechanism)
  - ❌ current experiment, dripfeed export of ADVANCED_CIRCUITRY, and dripfeed import of ELECTRONICS and MICROPROCESSORS. 
    - ❌ market is already in "growing" state already
  - if the above experiment does not yield growth before the profit margin tanks, then we will need to start by evolving the extractor based markets instead, wide base.
  
## EXPERIMENT 
CTRI-C vs CTRI-V 
single commander - check we're not sharing systems.
C - trade whenever there is any profit to be made
V - trade only whenever there are maximum margins to be made. 


### Fuel costs
Problem: Fuel is absurdly high, and unexpected latency intolerance meant that my initial EXPLORE command didn't execute overnight.



### projects paused mid development
✅🥇We started on a new event throttler, which is paused for the time being.
We also started trying to do pathfinding for intrasolar, it's kind of done but in some cases ships still go drifting when they shouldn't.


End of week stats

| stat         | Node U | node V | node C | 
| ---          | ------------ | ---------- | --------------- |
| total uptime |  188.67h   | 131.24h | 103.51h |        
| total ships  | 84         | 3        | 2
| contracts    | 0          | 0        | 0
| earnings     | 59,777,850 | 569,494  | 0
| requests     | 640,007    | 36,904   | 74,664
| average delay| 2.37       | 0.43     | 0.31
| CPH          | 3,396      | 280      | 0
| CPR          | 93.4       | 15.43    | 0