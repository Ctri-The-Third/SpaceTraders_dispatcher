Learnings from last week

* ✅ Contracts are good if we have enough money to execute them
* relying purely on the "manage export" behaviour is not good if the suppyling tradevolume is equal to (or less than) the hungry tradevolume, especially for manufactured materials.
* Our "build a jump gate" behaviour is functional - we'll definitly get the jump gate done this reset.
* we were vulnerable to an early game stall - fixed by minimum safety amounts, and buying fewer ships to begin with.
* during volatile trading with multiple active ships, it was possible to sometimes have no money to buy fuel. We added a minutely retry in this circumstance, and it's shown usefulness in preventing drifts.



✅ I'm going to implement a "chain trade" behaviour, expanding off the old "single stable trade" concept. Essentially, the commander will pinball between the stations in a chain, buying exports and selling them to matching imports until it eventually reaches a market without any exports. At that point, it'll try and find a profitable exchange based market selling raw goods and start a new chain - until there are no profitable exchanges left (which shouldn't happen if there are siphoners or extractors)

In the event there are no profitable exchange starting points, picking the nearest profitable  trade is a good fallback. 
Outcome: Incredibly effective. 🥇

Our planned strategy was: 
> let's do:
> * ✅ commander does chain-trade
> * ✅ buy 5 siphoners for the gas giant
> * ✅ buy hauler and manage explosives 
> * ✅buy hauler and manage metal refineries
however, an error in deployment meant the Node V (Week21) strategy was executed instead, triggering a stall.
Whilst "Chain trade" has proven effective, when working with credit values less than 500, it's better to EXTRACT_AND_SELL, so I've created and EMERGENCY_REBOOT behaviour that will have the commander EXTRACT_AND_SELL from the gas giant to the fuel refinery - to help guarantee that we have sustainably priced fuel. 


## REUSING BEHAVIOURS
**Musings:**

I already have a good "buy and sell" behaviour. Why not use the chain behaviour like a micro conductor? it can determine where we're at, consult the DB, and then feed that information into the behaviour params for "buy and sell". everything will be under the same session ID but there will still be two BEGIN events, so manybe not :thinking:

unless!
we just inherit the "buy_and_sell" behaviour instead of "generic behaviour" and use the fetch half and deliver half methods respectively. 

Rather than having the Chain_Trade behaviour call buy_and_sell, it just has access to those methods and flexibility in how it uses them.
this keeps the logging clean.

**Outcome:**
When I went to implement the "manage contracts" behaviour, I realised I was doing enough of the same stuff that I put the "fetch_half" and "deliver_half" into the generic behaviour class after all.

## MARKET GROWTH
**Musings:**

I'd already come to the conclusion that I needed to focus market growth behaviour on the base layers of the production chain rather than the highly profitable end-products. Chain Trading is largely taking care of the high-value stuff, and leaving the raw materials to slowly gather their requirements is definitely the best way forwards.

So far, I see that the two explosives imports (nitrogen and hydrogen) are doing well with supplies of LIMITED and MODERATE respectively. Their tradevolumes are at 60 and will need to rise to 180 before the export of explosives can rise beyond its current of 60.

Likewise the fuel market is in a good state from our work doing EMERGENCY_REBOOT earlier, with an ABUNDANT impport (and crashed prices) and a healthy set of export options. 
We'll see if the import for that on evolves. Fingers crossed!

**Outcome:**
Remains to be seen.
So far I'm observing the following moving out of the default WEAK state
IRON_ORE (GROWING) which feeds IRON (STRONG)
ALUMINUM ORE (WEAK :( ) which feeds ALUMINUM (GROWING)
COPPER_ORE (WEAK :( ) which feeds COPPER (GROWING)
HYDROCARBON (GROWING) which feeds FUEL (WEAK)
LIQUID_NITROGEN (GROWING) which feeds EXPLOSIVES (WEAK)
LIQUID_HYDROGEN (GROWING) which feeds EXPLOSIVES (WEAK)

HOWEVER, unexpectedly the code has diverted haulers away from that behaviour. 
We had a bit of code that checked there were valid places to sell the managed EXPORT, but that was predicated on the assumption that there would always be a profitable route for the export.
If we still need to work on the import whilst the EXPORT is fulfilled, then this code takes haulers away too soon.

Whilst it is good to have a mechanism by which ships can be redirected to more profitable activities - this is not the correct way to do it, so I'm removing that function and reverting to just the fixed strings.