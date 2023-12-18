
* `git clone git@github.com:whyando/spacetraders1.git`
worked without issue

* `./run.sh`
> 2023-12-18_09-53-27  
> Server 'node src' crashed with exit code 0.  Respawning..

* Tried updating to the latest version of node, but that didn't help.
Need to run a setup command first?


* `npm i`


* `node src CTRI-S-` 
```
Error: DB_URI not set
    at file:///home/ctri/SpaceTraders-Whyando/src/config.js:8:11
    at ModuleJob.run (node:internal/modules/esm/module_job:218:25)
    at async ModuleLoader.import (node:internal/modules/esm/loader:329:24)
    at async loadESM (node:internal/process/esm_loader:34:7)
    at async handleMainPromise (node:internal/modules/run_main:113:12)
```
looks like it needs a connection string for postgresql. 

* Commenting out the DB code appears to have worked.

* Had to move the commander to A2 to facilitate probe buying

OBSERVATIONS:

He has a "Universe" object that contains all systems and waypoints, surveys, markets, and shipyards.
He has agent specific configurations with things like the following
```
       CONFIG.num_supply_trade_haulers = 2
        CONFIG.num_supply_trade_v2_haulers = 2
        CONFIG.enable_probe_market_cycle = false
        CONFIG.num_trade_haulers = 1
        CONFIG.num_siphon_drones = 10
        CONFIG.enable_gate_builder = false
        CONFIG.cmd_ship = 'none'
```
From this we can see his last-week behaviour was 4 haulers, 1 trade hauler, 4 supply haulers, 10 siphon drones, and no behaviour on the command ship.

To set a starting faction the syntax is `node src agent:faction`

It seems that config values can be edited in real time without a restart - that's pretty cool. We could see about saving our "next update" timestamps to a local file and having a "hard reset" flag. That way we can relatively seamlessly restart the conductor with new changes.
having behaviour as adjustable config is a very smart idea.

* on initialisation, does a sweep of all markets & shipyards in the starting system.
* Then based on the config, a number of jobs are created. (these are like behaviours, but unallocated, set to the first available ship_type that is available)

* ship_types are initialised from the code with an engine, a frame, and their mounts as criteria - so a ship_type is a collection of engines, frames, and mounts.
* Ships are assigned to ship_types based on their configuration (similar to our populate_ships method in the conductor)
* Ships that are not linked to jobs are then given those jobs based on their priority. Priority is only used for making waypoints go to shipyards first and markets second.
* jobs look like this - that's behaviour ID, then parameters  
```[
  "idle_probe/X1-XA77-A2", 
  "idle_probe/X1-XA77-H50",
  "idle_probe/X1-XA77-C39",
  "trading/X1-XA77/1",
  "supply_trading/X1-XA77/1",
  "supply_trading/X1-XA77/2",
  "supply_trading_v2/X1-XA77/1",
  "supply_trading_v2/X1-XA77/2",
  "siphon_drone/X1-XA77/1",
  "siphon_drone/X1-XA77/2",
  "siphon_drone/X1-XA77/3",
  "siphon_drone/X1-XA77/4",
  "siphon_drone/X1-XA77/5",
  "siphon_drone/X1-XA77/6",
  "siphon_drone/X1-XA77/7",
  "siphon_drone/X1-XA77/8",
  "siphon_drone/X1-XA77/9",
  "siphon_drone/X1-XA77/10",
] ```


* It will then go through all unassigned ships and assign them to the first matching job.
* 