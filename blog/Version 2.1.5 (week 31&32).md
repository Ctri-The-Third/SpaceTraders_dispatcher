# Week 31/32

We can now set behaviours individually, and Space Admiral has sorted some more of interstellar trading.

Unfortunately, for reasons as yet unclear, the Node-U behaviour didn't properly start executing TRADE_BEST_INTRASOLAR for the command ship.
With Justin back and active (and already in first place), the focus is going to be largely on enhancing reliability and performance, not new strategies.

Node-V isn't doing anything at all, when I restarted the dispatcher I got a bunch of errors from it attempting to map to a system it's not in?  
Turns out we need to purge the cache between resets. Maybe the clint should do that if the system's dates don't match up with the service?

## performance

| stat              | Node U (exp) | node V (26-27) | node C (27-28) |  
| ---               | ------------ | -------------  | -------------- | 
| total uptime      | 
| total ships       | 
| contracts         | 
| contract_earnings | 
| trade_earnings    |
| total_earnings    | 
| requests          | 
| average delay     | 
| CPH               | 
| CPR               |
