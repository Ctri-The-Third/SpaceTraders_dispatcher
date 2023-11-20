

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

we had to restart essentially from scratch by cutting off the dispatcher and drift navigating some marginal trades until we were making enough profit per trip to cover fuel costs and switching back to cruise speeds.

I think our early stage game needs to be 
* ✅ Explore the system
* ✅ Shave off the top of profitable trades (continual)
* Afford up to 10 siphon drones (extract and chill)
* Afford 1 hauler for delivering to the gas giant
* Afford up to 10 mining drones (extract and chill)
* Afford 1 hauler for delivering to the gas giant
* Afford 1 surveyor
* for each end-tier product, afford 1 shuttle per branch and start continually shifting goods A -> B -> C -> D (not A -> B, back to A without a tradegood)

From there we can theoretically fabricate everything and should map out the supply chains necessary to do so, and use shuttles (initially) to move those goods around, until we hit 100 trade volume (at which point we start using Haulers instead)