# version 2.1

This has broken a significant portion of the SDK. The main breaking points are changed models.
I'm going to use the Dispatcher and Conducter from week 16 to get behaviours up and running, and each crash will be met with a pair of integration tests for the API and Database respectively.

This will help in rapidly identifying and correcting future changes to the SDK.

I've decided that I'm going to match the SDK models to the new changes, even if that breaks backward compatibility. The number of calls necessary to properly replicate the 2.0 models would incur technical debt, and I'd rather just take the hit now.

I've noticed that everything breaking has triggered the "setback effect", which was identifed as the primary risk to this project losing momentum and wandiner off. Therefore the response to this patch, which is happening in the middle of tumultuous life events, is going to be key to whether or not we continue playing SpaceTraders or not.

## Step Zero - Afford a Hauler
- ✅ Looking at earning credits, fuel _seems_ like it'll be a large impact, with refuels needing to happen repeatedly.
- ✅ I think we can buy hydrocarbon and sell it to the refinery, which will give us a place to buy fuel that's reliably cheap
- ~~no I'm getting off target. We can just consider jettisonning the things that aren't worth the CPS to sell.~~
- then we'll be able to get a siphoner drone and use that to increase our rate of getting hydrocarbons
  - On later reflection I've decided that the value add from a siphoner is less than the value add of a hauler being able to meet the waypoint trade requirements.
   - A player on the discord mentioned they were seeing substantial reward from balancing all the need from the markets in the system, so I'm exploring that option as my foudnational strategy.
- ✅ then we'll be able to get a hauler and use the command frigate for mining

## Step One - Build the jump gate
-  ✅ Our first step is to get the Dispatcher and Conductor working without crashing.
- Secondly we'll want a very rudimentary drone based solution to get credits flowing in.
  - ✅ we should target the nearest asteroid, not the first one returned by the DB.
  - fairly sure my first extractor is drifting to the target asteroid - need set in some behaviour for flight-mode handling for drones.
  - I've decided our fleet goal will be 10 extractors, 2 surveyors, 1 transporter. will need to do analytics on the effectiveness of this.
  - I'm going to skip upgrading behaviour for now and turn that off. Specifically all the values have changed and I want to make it less hard coded and more compatible with an aribtrary ship configuration coming in.
- Our "ships we might buy" assumes multiple shipyards automatically. In the early game, only one probe is needed, buying 2 extra has negatively impacted things.



# Difficulties & Solutions
The problems we faced, the reasoning behidn the solution, and the observed outcomes.




### disparate sell points

In version 2.0, you could sell pretty much everything you extracted at a single marketplace.  
However in version 2.1 you need to visit multiple markets to sell everything.

Problem: The behaviour only supports a single sell point per execution
Problem: The behaviour has no support for jettisonning unsellable cargo
Problem: The behaviour is not smart about which cargo to prioritise extracting and selling. 


Solution: Conductor should look at markets, proximity of source, and value of cargo to determine where to mine, where to sell, and what to sell.
```
Select all asteroids in system.
For each asteroid, determine the things it CAN supply based on traits. 
For each supplyable, determine CPS of travel time (assume immediate and perfect extraction)
Record each asteroid's sell CPS, and assign to fleet groupings accordingly.
```
Solution: Default behaviour should try and sell everything, and jettison anything it can't.
Solution: Update the "Sell All" behaviour to only sell cargo the marketplace will accept.

### We never actually trade
 
Presently we're asumming that the best time spend for us is extracting and selling.
However, I think at this early stage of the game with small markets and small cargo bays, we should be using the command ship for trading.

Problem: Trade opportunities definitely exist, but we're not taking them.
Solution: ✅ Switch drones to "Extract and go sell" behaviour 
Solution: ✅ Switch haulers to free "trade_intrasolar" behaviour
Solution: Switch "Receive and fulfill" behaviour to **take** desirable materials from nearby extractors / refineries - lets conductor send haulers to extractors when they're nearly full.



Problem: Haulers sitting idle at waypoints waiting to receive cargo
Solution: Get inventory info into the DB & forcibly extract desirable cargo from haulers.


### We started trading but made bad trades

Problem: I woke up this morning with no money, and the command ship isn't able to execute trades anymore because of this.

Looking at the numbers overnight it seems that the money went to buy surveyors that shouldn't have been bought - a conductor issue.
Additionally, it doesn't actually seem like we made bad trades after all, just that the surveyor purchases undercut the operating capital requirements for the trade.

Solution: When assigning trades, keep track of the assigned ship's cargo capacity & current trading costs, and ensure that there's a minimum operating capital kept in the bank.
Solution: Quick solution - have the buy/sell behaviour check if a trade is still going to be profitable _at all_ before making the trade. 
Solution: Proper solution - Dispatcher overhaul, behaviours get termination events, infinite loops after setup, and the dispatcher sets the terination event if the behaviour changes.