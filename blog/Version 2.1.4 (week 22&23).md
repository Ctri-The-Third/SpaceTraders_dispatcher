

goals for the week - 
* Complete as many missions as possible
* evolve markets

# Week 22 - Version 2.1.4
After last week I have a solid understanding that gameplay needs to focus on keeping markets un restricted.
I also recognised that transport shuttles were woefully inadequite at handling trades, and that we'll swap to a more expensive hauler based model for this week.

I intend to have node U as my experimental node, node V as my control node running last reset's code. Half way through the reset I'll deploy my experimental code so far to node C.


## Rocky start 

The working capital safety didn't get respected by the minutely update, unfortunately. This means that we're currently trading below capacity.

I made the decision to focus ship_parts and ship_plating, as the exports outweigh the import trade_volumes, so we should be able to ramp that up fairly early on without needing to evolve the supplying imports.

Ships are scaling up though. We have enough probes, and are slowly building our siphoners.  I realised with tha co-located exchange for the siphoners, there's no reason to use "siphon_and_chill" when I could use "extract_and_go_sell". This is ensuring that despite operating below the safe limits, we'll be able to afford fuel for timely trading. We'll need to alter our mining packaging behaviour and maybe look at ships who have been immobile for a little while or something.

We'll need to remember to have ships that can sit on that exchange and sell the stored goods when the reach suitable prices. The exchange will take some margin, but the uncoupling this allows is definitely going to be worth it.

When we get mining drones, will need to factor in proximity to a market as well, if we can find one that is <40 units we'll be in a good place. If we do <80 units we might need to be clever with fuel.

* Currently we're setting the commander to manage an export immediately, instead of fuel. The commander is running out of things to do when the market is not valid for managing that export. Currently this is because the behaviour does not factor getting imports into the market unless the market is restricted.
* The conductor needs to track permanent assignments and assign priority based tasks until they're complete. 
* single trading tasks should have a FUEL_ requirement that is the largest single hop in the pathfinder. 
* QUESTION - should we just switch to a task based system, and fall back to behaviours?
  * much harder to troubleshoot.


## node V 

We missed some early behaviours with node V, and unfortuantely it's not generating any credits. I'll need to look into why the contract tasks aren't being picked up by the dispatcher and maybe fix that one thing tomorrow.


## tracking progress on market growth and changes.

✅ I want a system-wide view of tradegoods and their market states. 
Clicking into them should show an interweaved set of transactions, and activity /supply changes on a minute to minute basis, as well as any ships responsible for making those transactions.

✅ I want to be able to see which markets are restricted.
s
 A per-listing graph showing the export market(s) and the import market(s) with their prices over time, supply state, and activity stat should be provided.
now a mechanism that, for each of these exports, shows the dependancy chain and their states. 
State health calculated by 
* Activity (if not restricted)
* No items sold (if > 0 )
* Supply 

## Complete restriction

Our increase to haulers has seen several markets enter the STRONG state, those are FOOD, ALUMINUM, and ALUMINUM_ORE.
What we don't have is a way to observe both the behaviours for a given ship, and and the transactions for a given market.
Unfortunately, later those returned back to a RESTRICTED state and it's not quite clear why. 

* ✅ We need to get EXPLOSIVES managed, who will gain their IMPORTs from exchanges.
* ✅ A new view which shows transactions, and can be filtered either by tradegood, or by market.
* ✅ Update the SDK so that behaviour params are logged with the event's beginning.
* We now need to get ship sessions summarised and then surfaced in the UI so we can troubleshoot better. the current view looks meh
* ⏳🤷‍♀️ The amount of quarterly quests was definitely clogging things up. It might be better to have a floating hauler (or the commander I guess) that is set to zip between markets and perform profitable trades - with the rest managing exports
* I noticed that the Food export keeps going to buy fertilizer at a 600cr / unit loss, and that fertilizer isn't seeing any management.
  * ✅ switched off the quarterly tasks
  * ❌ should hopefully see more fertilizer management now.
  * ✅ Not enough nitrogen and stuff being brought in - need to review the behaviour
* ✅ We should start working on the jump gate now we have sufficient money.
* ✅ We're becoming over-reliant on the task system, and should decrease the amount of unpredictability that systme engenders. It's designed for one offs - and whilst it's useful during setup for things like shallow trades and earning cash, we should switch that off once we're not at risk of stalling.
* ✅ Create a "go and refuel this stuck ship" task to support extractors that are out of fuel.
* ✅ Ships are failing to do moves because of insufficient fuel, and default to drifts immediately afterward. Whilst it's good that the fallback behaviour is working, this is an issue.
* ✅ Revisit the "manage exports" behaviour so that it can also source imports from exchanges, and stops doing unprofitable trades.
 * profit from the system as a whole has dropped since we lifted the text based restrictions and went to profit only. This appears to largely because of multiple ships relying on individual exports as their imports and the exports not being able to keep up.
* ✅ I've noticed several market exchanges where tradevolume IMPORTs are _equal_ to the tradevolume of the EXPORTs, but we know from Space Admiral that this ratio needs to be closer to 3:1, so we should build behaviours that are going to properly handle this situation.
* We switched asteroid-0 extractors to "EXTRACT_AND_SELL". If there's an exchange within 80 units of travel, we'll use that instead of "EXTRACT_AND_CHILL".
* I've created a mining sties view in the DB - which lists an asteroid and its yield, along with imports/ exchanges (and their distances). This will inform the range of EXTRACT_AND_SELL groupings - need to scale that up.
* I've observed that using light haulers for missions is not optimal. Idle trade ships should have the following behaviours
 * 1 ship has a "complete missions then chill" behaviour. If there is not a profitable mission at present, the conductor should skip this step.
 * 1 ship should have a "Construct warp gate" behaviour. 
 * other ships should have a "chain trade" behaviour, which will pick a profitable trade from the current location, then execute it - or look for raw materials to feed into the chain.
 

TOMORROW TASKS 

 * We should increase the amount of concurrent miners operating near exchanges.


End of Week reports.
Node U - current reset, experimental
Node C - current reset, executed half way through
Node V - end of week 21 (last reset)
Node S - end of week 23 (reduced usage of tasks, contracts support, jump gate gets built)
Node W - idle 
After this reset we'll put this onto node S. 

| stat              | Node U (exp) | node V (21) | node C (22 halfway) | 
| ---               | ------------ | ----------  | --------------- |
| total uptime      | 140.44       | 253.19      | 184.03          | 
| total ships       | 76           | 59          | 74              |
| contracts         | 60           | 0           | 2               | 
| contract_earnings | 17,140,049   | 35,397      | 1,183,332       |
| trade_earnings    | 48,250,860   | 69,471,819  | 10,348,853      |
| total_earnings    | 65,390,909   | 69,507,216  | 11,532,185      |
| requests          | 901240       | 1044219     | 425277          |
| average delay     | 2.04         | 4.47        | 1.40            |
| CPH               | 465,614.56   | 274,525.91  | 62664.70        |
| CPR               | 72.56        | 66.56       | 27.17           |