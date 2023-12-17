Learnings from last week

* Contracts are good if we have enough money to execute them
* relying purely on the "manage export" behaviour is not good if the suppyling tradevolume is equal to (or less than) the hungry tradevolume, especially for manufactured materials.
* Our "build a jump gate" behaviour is functional - we'll definitly get the jump gate done this reset.
* we were vulnerable to an early game stall - fixed by minimum safety amounts, and buying fewer ships to begin with.
* during volatile trading with multiple active ships, it was possible to sometimes have no money to buy fuel. We added a minutely retry in this circumstance, and it's shown usefulness in preventing drifts.



I'm going to implement a "chain trade" behaviour, expanding off the old "single stable trade" concept. Essentially, the commander will pinball between the stations in a chain, buying exports and selling them to matching imports until it eventually reaches a market without any exports. At that point, it'll try and find a profitable exchange based market selling raw goods and start a new chain - until there are no profitable exchanges left (which shouldn't happen if there are siphoners or extractors)

In the event there are no profitable exchange starting points, picking the nearest profitable nearby trade is a good fallback.

Our planned strategy was: 
> let's do:
> * ✅ commander does chain-trade
> * buy 5 siphoners for the gas giant
> * buy hauler and manage explosives 
> * buy hauler and manage metal refineries
however, an error in deployment meant the previous strategy was executed instead, triggering a stall.


## REUSING BEHAVIOURS
**Musings:**

I already have a good "buy and sell" behaviour. Why not use the chain behaviour like a micro conductor? it can determine where we're at, consult the DB, and then feed that information into the behaviour params for "buy and sell". everything will be under the same session ID but there will still be two BEGIN events, so manybe not :thinking:

unless!
we just inherit the "buy_and_sell" behaviour instead of "generic behaviour" and use the fetch half and deliver half methods respectively. 

Rather than having the Chain_Trade behaviour call buy_and_sell, it just has access to those methods and flexibility in how it uses them.
this keeps the logging clean.

**Outcome:**
When I went to implement the "manage contracts" behaviour, I realised I was doing enough of the same stuff that I put the "fetch_half" and "deliver_half" into the generic behaviour class after all.