# Week 29/30 

It's unclear how much spare time we'll have this coming fortnight, but what time we have is going to be spent on the UI adding user facing controls to the system.

Once that's completed, a mechanism by which the user token can be used to instantiate a new dispatcher 

Progress on the UI to enable ship controls is going slowly and unsteadily.  
It feels like a simple task that will take a lot of time, and as such there's quite a mental barrier against it.  
The solution will be to gently chip at it, with each bit of progress making the system more functional than the last - doing it all in one go is not a viable option (psychologically) so breaking it down is the way forwards.  
✅ We can already set individual tasks - which is a huge step forwards, we just need to get the UI to be able to set behaviours instead and buy ships, and we'll be functionally comparitive with the conductor.  


## performance

* Node U (exp 29-30) - Didn't do initial exploration - why?
  * The evolution behaviour appears to be buying goods when it's at the end of the chain and there's no profitable location - so it ends up selling them at a loss next time around
  - ✅ sorted itself out, ran out of money initially but caught up once TVs eveolved.
  - ✅ seems to successfuly build jump gate and explore the gate network outwards.
  - needs to find heavy haulers
  - needs to trade antimatter
  - needs to warp to start systems.
* Node C (27-28) - Didn't do initial exploration - why?
 - it sorted itself out, but ran into issues with fuel distribution
 - didn't build jump gate.

* Node V (26-27) - Didn't do initial exploration - why?
 - stuck doing mining and no trading
 
| stat              | Node U (exp) | node V (26-27) | node C (27-28) |  
| ---               | ------------ | -------------  | -------------- | 
| total uptime      | 335.92       | 182.43         | 336.49         |
| total ships       | 102          | 27             | 42             |
| contracts         | 377          | 0              | 0              |
| contract_earnings | 38,708,976   | 0              | 13404          |
| trade_earnings    | -2,457,452?? | 1,454,525      | 41,500,535     |
| total_earnings    | 36,251,524   | 1,454,525      | 41,513,939     |
| requests          | 443,175      | 194,175        | 1309062        |
| average delay     | 11.94        | 0.54           | 1.85           |
| CPH               | 107,917.13   | 7,973.06       | 123373.47      |  
| CPR               | 81.79        | 7.49           | 31.71          |
