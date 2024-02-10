# Week 29/30 

It's unclear how much spare time we'll have this coming fortnight, but what time we have is going to be spent on the UI adding user facing controls to the system.

Once that's completed, a mechanism by which the user token can be used to instantiate a new dispatcher 

Progress on the UI to enable ship controls is going slowly and unsteadily.  
It feels like a simple task that will take a lot of time, and as such there's quite a mental barrier against it.  
The solution will be to gently chip at it, with each bit of progress making the system more functional than the last - doing it all in one go is not a viable option (psychologically) so breaking it down is the way forwards.  
We can already set individual tasks - which is a huge step forwards, we just need to get the UI to be able to set behaviours instead and buy ships, and we'll be functionally comparitive with the conductor.  


## performance

* Node U (exp 29-30) - Didn't do initial exploration - why?
  * The evolution behaviour appears to be buying goods when it's at the end of the chain and there's no profitable location - so it ends up selling them at a loss next time around
  - sorted itself out, ran out of money initially but caught up once TVs eveolved.
  - seems to successfuly build jump gate and explore the gate network outwards.
  - needs to find haulers
  - needs to trade antimatter
  - needs to warp to start systems.
* Node C (27-28) - Didn't do initial exploration - why?
 - it sorted itself out, but ran into issues with fuel distribution
 - didn't build jump gate.

* Node V (26-27) - Didn't do initial exploration - why?
 - stuck doing mining and no trading
 
| stat              | Node U (exp) | node V (26-27) | node C (27-28)
| ---               | ------------ | ----------  |
| total uptime      | 257.29       | 354.16      | 
| total ships       | 84           | 22          | 
| contracts         | 257          | 2           | 
| contract_earnings | 22,025,637   | 0           | 
| trade_earnings    | 148,474,606  | 2,692,372   | 
| total_earnings    | 170,500,243  | 2,692,372   |
| requests          | 1,218,532    | 392,857     |
| average delay     | 9.01         | 0.5         | 
| CPH               | 662,677.30   | 7,602.134   |
| CPR               | 139.922      | 6.85        |
