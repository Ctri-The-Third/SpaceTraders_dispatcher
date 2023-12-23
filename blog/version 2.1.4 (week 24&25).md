
# week 24 & 25

## Learnings from last week
* ✅ Contracts are good if we have enough money to execute them
* ✅ relying purely on the "manage export" behaviour is not good if the suppyling tradevolume is equal to (or less than) the hungry tradevolume, especially for manufactured materials. 
 * There are 3 TV 60 Aluminum imports and 1 TV 60 Aluminum export. Whilst I hope that extractors will speed this up, having such a grotesque imbalance was the reason for our losses last fortnight.
 * We should apply analysis behaviours to the corresponding TVs before managing the next export up a chain.
 * IRON has grown, but ALUMINUM hasn't - why? let's plot the price differences between  hungry imports and their supplying exports, same with exports - preferably on a box chart.
  * It did eventually grow! They're all sitting at 123 export tradevolum and 180 import tradevolume.
* a STRONG market produces goods (changes prices) at between 2 and 4 times the speed of a RESTRICTED market. we must prioritise keeping markets out of the the RESTRICTED state, but also be aware that a STRONG market will innvitably grow if prices are less 80% of the max price. Thus, ABUNDANT trading is the best way to keep markets we're not evolving, producing the best we can. Markets that are strong should always be ABUNDANT tradd, and markts that are RESTRICTED should be left more flexible. 
* Having a chain trader that focuses on restricted markets (Even if they're going to be less profitable less frequently) is a good way to keep things flowing. Specifically, something that prioritises SCARCE then LIMITED imports should keep the exports out of the RESTRICTED state.
*  Our "build a jump gate" behaviour is functional - we'll definitly get the jump gate done this reset.
* we were vulnerable to an early game stall - fixed by minimum safety amounts, and buying fewer ships to begin with.
* during volatile trading with multiple active ships, it was possible to sometimes have no money to buy fuel. We added a minutely retry in this circumstance, and it's shown usefulness in preventing drifts during exceptional situations.
TODAY TASKS:
* ☑️ see if we can get Justin's code running on node S(espionage)
* ☑️ implement monitoring script into node S
  * ☑️ movement, ⌛purchases, ⌛sells, ⌛contracts.
* ✅ Add return trip planning to extract_and_sell behaviour.
* Generate historic chart of specific manufacturing element.
  * EXPORT tradevolume, price, supply & activity.
  * IMPORTs tradevolume, PRICE & COMPARISON TO SUPPLY, supply & activity.
* build a "supply chain trade" behaviour that takes a specific end product and calculates all the requirements, buying and selling up the chain.
* Note that pure Chain Trading with more than 2 ships at the TradeVolume's we're working with, starts to cause price collision and bad trades. 
  * We could work around this by having a singleton trade reservation manager that just keeps track of who's doing what, and says no to ships who want to do the same thing.

## Obsrvations of previous behaviours

* NodeC had its satelites deploy on a daily refresh, which meant there was many hours between a satellite coming online and it being given instructions
 * To combat this, nodeU reinstruments behaviours every time a new satellite comes online 
* Node C has run out of money because of construction trades
* We previously used "dripfeed" technology to keep prices around their maximums. I'm putting something similar into the chain-trade, specifically filtering it 
✅ I'm going to implement a "chain trade" behaviour, expanding off the old "single stable trade" concept. Essentially, the commander will pinball between the stations in a chain, buying exports and selling them to matching imports until it eventually reaches a market without any exports. At that point, it'll try and find a profitable exchange based market selling raw goo

## Chain Trade
✅ I'm going to implement a "chain trade" behaviour, expanding off the old "single stable trade" concept. Essentially, the commander will pinball between the stations in a chain, buying exports and selling them to matching imports until it eventually reaches a market without any exports. At that point, it'll try and find a profitable exchange based market selling raw goods and start a new chain - until there are no profitable exchanges left (which shouldn't happen if there are siphoners or extractors)

In the event there are no profitable exchange starting points, picking the nearest profitable  trade is a good fallback. 
ds and start a new chain - until there are no profitable exchanges left (which shouldn't happen if there are siphoners or extractors)

In the event there are no profitable exchange starting points, picking the nearest profitable  trade is a good fallback - if we add some randomness to it.
When we were chain-trading the best available export -> import, we had collisions. Now we've made it random, we're doing dumb things like trading fuel between exchanges.

**Outcome:** Incredibly effective. 🥇
This is shaping up to be the best addition to the script this reset. We've had two full stalls this go around
1. because we deployed the wrong conductor and bought a tonne of ships we didn't need/ want
2. because of an edge case, too many haulers were concurrently instructed to build the jump gate, and we emptied our money on ADVANCED_CIRCUITS

In both cases, the CHAIN_TRADES behaviour was crucial in getting things back on track. The first one required a combo of the EMERGENCY_REBOOT behaviour to keep the lights on, and the latter we didn't intervene beyond fixing the code issue, and after 4 hours the system had recovered itself to the point of the command ship (and additional freighters) running full loads again.

## Unlocking the Jump Gate

It's wednesday (3 days into the reset) and we're going to complete our jumpgate this evening. Excellent news. 
Here's what I'll need to get underway - and eventually have procuedurally detected by the conductor.
* ✅Take the commander to the faction HQ to buy explorers
* ✅get a list of accessible HQ systems (those with jump gates and >= 15 planets)
* ☑️Send an explorer to each (preferably by jump gate, if not figure out warping)
* ☑️update the "explore" system with chart behaviour. Don't chart any of the rare goods markts or shipyards that contain non-standard ships.
* ✅Once there, chain-trade.
-----
* ✅ Need a way to spot probable systems with healthy lots of trade opportunities - ah! Engineered asteroids.
* Evntually, go exploring for the unlinked systems around the home system - see what they've got.
* Eventually, send orehounds home to mine the farther asteroids and bring to exchanges. Ships bought should be assigned to a system by the conductor with a task.

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

So far, I see that the two explosives imports (nitrogen and hydrogen) are doing well with supplies of LIMITED and MODERATE respectively. Their tradevolumes are at 60 and will need to rise to 180 before the export of explosives can rise beyond its current of 60 - at the time of writing 150 and 165 respectively.
However, the EXPLOSIVES export is still showing as RESTRICTED, and the supplies are mostly scarce. I'm also seing tha

Likewise the fuel market is in a good state from our work doing EMERGENCY_REBOOT earlier, with an ABUNDANT impport (and crashed prices) and a healthy set of export options. 
We'll see if the import for that on evolves. Fingers crossed!

**Outcome:**
Understanding, validated by the developers. 🥈 very good, work to be done.
Market prices update every 15 minutes, which is also when ACTIVITY and SUPPLY calculations are made.
Goods that are STRONG change their prices between 2 and 4x the rate of goods that are RESTRICTED. 🚨This is not yet public knowledge.🚨
Import goods will not grow to be more than 3* the tradevolume of the export, nor will they evolve with a supply of more than 80% (price is > 80% of max price)
Export goods will not grow to be much less than 2:1 of the import tradevolume 
An amount of time is needed for the market to be in the GROWING state before it will become STRONG, and enable growth. 


## Espionage ##

Another player, Justin, has observed a huge CPS spike in their system. It's not clear why or how, but understanding is key.
They've shared their respository on github so I'm going to spend some time looking at their code and seeing if I can figure out what's going on.
Might be possible to modify it to add PostGres logging to mine, but it's written in another language so this will be extremely challening and probably not worth it.

I think instead I'll just use my SDK to regularly ping my copies of his ships and build retroactive logs of what's going on. Better! I can identify his system, drop an agent in that system and begin monitoring the markets' "transaction" histories.

**Outcome:** 
Their conductor is configurable and the configuration doesn't live in the repository well - so determining his strategy is impossible.
They've put restrictions on their chain-traders so it only does MODERATE or ABUNDANT trades compared to our any% - I'm implementing this myself  
They have a probe that pings markets on a loop instead of our static sentries - going to keep with my own system
They have 5 haulers doing chain trades instead of my 1 (and managed goods) - I'm going to investigate a SUPPLY_CHAIN_TRADE behaviour

We need to properly estimate the capacity of a given system for concurrent traders. This needs to factor in tradevolume, and total distance between imports and their exports.

--- 
# Intergalactic operations

* We're hampered by a UI and conductor not designed for multi system operations. Each system we select should be managed. Ideally, this should be shared across agents
* we need to be able to set jobs on a per-system basis, with requirements.
* This week we're using explorers but we should have an intermediary step of finding haulers on the jump gate network. 
* Identifying starter systems is easy to a human. They have planets with a consistent naming structure, an engineered_asteroid and operate with at least 15 planets/moons.
  * The non-starter systems that are on the jumpgate network must be explored. Probes may be the best choice for this as they're cheap and the jumpgate is inherently slow anyway




# market evolution investigation



```sql
with changes as ( select event_timestamp
, event_params ->> 'market_symbol' as market
, event_params ->> 'trade_symbol' as trade_symbol
, event_params ->> 'activity' as activity
, event_params ->> 'supply' as supply
,(event_params ->> 'sell_price')::integer as sell_price
,(event_params ->> 'trade_volume_change')::integer as change 
, null::integer as goods_traded
  from logging l 
where event_name = 'MARKET_CHANGES'

-- --edit this-- --
and event_params ->> 'market_symbol' = 'X1-PK16-H57'
and event_params ->> 'trade_symbol' = 'IRON_ORE'
and (ship_symbol ilike 'CTRI-U%' or ship_symbol ilike 'GLOBAL')
-------------------
order by 3,2,1),

trs as (
	select timestamp, waypoint_symbol, trade_symbol, null, null,  t.price_per_unit, null::integer , t.units  from transactions t
	where ship_Symbol ilike 'CTRI-U%'
	and trade_Symbol in (select distinct trade_symbol from changes)
	and waypoint_symbol in (select distinct market from changes)
)

, combined as (
select * from changes

)
select c.*
-- and this - imports only
, round((sell_price/max_import_price)*100,2) as percent_of_best 
-----------------------------------
from combined c join trade_routes_max_potentials trmp on c.trade_symbol = trmp.trade_symbol
order by 2,3,1
```