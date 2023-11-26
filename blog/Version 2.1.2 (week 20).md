

goals for the week - 
* Complete as many missions as possible
* evolve markets

# Week 20 - Version 2.1.2

This week they added balance changes for market evolution. 
I observe a 3:1 ratio between imports and exports, instead of 10:1 as before.
They also added a "RESTRICTED" activity - an indicator that lack of imports are throttling the export.

at 1am we went from LIMITED to MODERATE and by 01:34 we had reached ABUNDANT, and continued to overfill that market overnight.

at 7am we intervened and began exporting the FUEL produced. 
note - the overabundance of HYDROCARBONS did not impact the export price / supply at all. 
at 07:22, the export trade evolume of FUEL evolved from 10 to 20, but the supply of HYDROCARBONS remains oversaturated.


Successful evolution of export starts by pushing the IMPORT supply beyond ABUNDANT, and if not crashing that market then certainly denting it past profitability.

The second step is to drop the EXPORT market down to SCARCE. If the two conditions are sufficiently met, then the EXPORT market will evolve.
the IMPORT market has not yet evolved.

We will continue exporting fuel (all the import markets are trade_volume 100 so there's no risk of crashing them), and see if either market evolves.


--- 

## the crash

This morning I ran out of money. monitoring behaviour over the course of the day, I believe the low prices of satellites and siphon drones dropped us below the minimum amount for shallow trades, perhaps even *whilst those trades were in progress*.

Additionally, and to finish things off, the hydrocarbons market crashed through oversaturation, even after reaching the next trade volume (30->60?)
so far we've seen 3,10,20,30,60,100 as trade volumes.

we had to restart essentially from scratch by cutting off the dispatcher and drift navigating some marginal trades until we were making enough profit per trip to cover fuel costs and switching back to cruise speeds. This has succeeded and we're now operating with a comfortable amount of money.

I think our early stage game needs to be 
* ✅ Explore the system
* ✅ Shave off the top of profitable trades (continual)
* ✅ Afford up to 10 siphon drones (extract and chill)
* ✅ Afford 1 hauler for delivering to the gas giant
* ✅ Afford up to 10 mining drones (extract and chill)
*  Afford 1 hauler for delivering to the gas giant
*  Afford 1 surveyor
*  for each "active planet" (e.g. start with the gas giant imports) buy a shuttle for each export and assign them to a route, repeat whilst profitable.

From there we can theoretically fabricate everything and should map out the supply chains necessary to do so, and use shuttles (initially) to move those goods around, until we hit 100 trade volume (at which point we start using Haulers instead)

until we have automated setup, we should manually
* ✅ set the siphoners to extract and chill
* set the shuttle to take_and_sell
* set the shallow trades to require a ship with speed greater than 3 (new dispatcher requirement)
* ✅ buy shuttles to take exports away from the refinery.



## Pathfinder issue

The last wee while I've noticed the odd journey being DRIFTed through, and now have figured out the cause thanks to a particularly straight line example.
I found a ship travelling to an end waypoint via an asteroid. The asteroid doesn't have any fuel, so why is it going there instead of drifting directly? or more preferably, going the long way around via some fuel stations? 

The cause is because the asteroid is a node that can visit both fuel stations, and is in between the fuel stations at a point where both legs of the journey are within the ships' theoretical maximum - it doesn't know that the 2nd leg of the journey will be made at DRIFT speeds.

The easiest solution will be as follows:
* ✅ Check if a single jump is possible without drifting, and if so - do that.
* ✅ If not, check the graph.
 * ✅ rework the graph so only fuel-to-fuel jumps get treated as non-drifting. The ship will still CRUISE, and there's a slight risk of ships going backwards to get onto the fuel network when not necessary - but I think the slight inefficiency there is worth it against the current DRIFT losses. The distance focused Heuristic might also end up protecting us from that.
 * 🥇 It's not perfect, but it is an improvement.




## Supply chain issues - raw imports & bottlenecks  

We've gotten a behaviour that manages exports, and have applied it to ADVANCED_CIRCUITRY, and its dependants - ELECTRONICS, MICROPROCESSORS and the dependant COPPER. 
Unfortunately, we need COPPER_ORE taken to the refinery and SILICON_CRYSTALS to the electronics/microprocessors factory. 

We don't have an easy way of doing this. Ideally haulers should go out to the asteroid belt, pick up a bunch of stuff from extractors, and bring it back.
Currently haulers are being given regular tasks to take stuff to the best market that will buy whats in the extractor inventory - but that doesn't include our single-import microprocessors factory. 


the conductor needs to know which raw goods are being actively consumed by which factories, and then we can assign haulers to manage their imports appropriately.

We need to provide 
 - Liquid Hydrogen and Liquid Nitrogen to the explosives factory
 - Siliocn Quartz to the electronics factory

✅ to do this we'll provide a behaviour that does the import management.