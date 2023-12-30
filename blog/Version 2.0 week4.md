# Week 4 

# Week 4 
Once this week is complete, I will have been playing for a month.

# Goals 

I'd like to tighten up the dispatcher from week 3 - it's almost in a good state. Both the dispatcher and the conductor struggle when a DB connection is lost, and we're now at two agents worth of infrastructure.
I'd like some visual display elements that auto refresh - much like metabase gives the refreshable dashboard.

Specifcs:
* Harden dispatcher and conductor to have auto-reconnect and auto-retry behaviour. ☑️
* Dispatcher should launch with args to specify which agent it's executing for. ✅
* Find out why the EXTRACT_AND_SELL script isn't registering that the ship is undocked ✅ (the extract command was doing an undock at too low a level)
* Callibrate conductor stage 3 to get ore hounds and freighters. ✅
* Have some way of excluding agents from the conductor - for ease of testing. (might be better to have a test DB - time to think about docker containers?) ✅ - (This is easy, just remove the conductor's access to the token for the user in question)
* Credits over time, per agent.
* Ship display, per agent.  (added some status views - these just need to be got from the db and spat out into a self-refreshing display of some kind.) ☑️
* Get the package compiling and installing. ✅
 
* conductor on nodeA for now
* Node A holds the database - we should move that to rasbee, and host (CTRI-A) on that.
* Node B should become the VPN node (CTRI-B)
* Node U remains the work node (CTRI-U)


# extract and sell_all (2) = 208.5530054644808743, 138.4804063860667634 when counting wasted behaviours
# combined behaviour (3) = 4.5, including wasted behaviours. GARBAGE. sob.
# extract_and_transfer_or_sell (4) AFTER we fixed surveys = 1943. Clear success over last week.
## Extract and Sell or Transfer

Needs the following things
* ✅ Surveys in DB (this is a big one for efficiency) 
  * ✅DB is in local time, ST is in UTC. Need to convert received timestamps to DB Time.  
  * ✅ This behaviour needs to automatically correct for BST/GMT 
* ☑️ Surveys from DB ( currently this is getting a good survey, but not the best survey) 
* Be able to find ships in DB from multiple agents
  * 
* dispatcher needs to get behaviour_params from the database. 


# End of week 4 

I've reworked my infrastructure a bit now.
For the time being, each node will run its own conductor and dispatcher - this will really simplify running restarts remotely.
We've got 3 IP addresses which can support agents running full time, with my home IP address free for a master user, or a test user for development.

I did some analysis of the behaviours.
* Extract and Sell all (week 2) worked out at about 138 credit per request. (with broken surveys)
* Extract and transfer all (week 3) combined with "Receive and fulfill" (week 3) worked out very poorly at 4.5 credits per request.
* Extract and transfer or sell (week 4) worked out at 1943 credits per request, which is awesome. However, this includes survey responses. Some callibration is needed to better assess the value of surveys and decide when to get one or not - as this could push Week 2's script up significantly.


I also hit my stretch goal of leaving the starting system. I deployed one of my command ships to visit all the jump gate systems that are connected.
It's slow going and we managed about 100 - and in the end did discover some new ship types - specifically `SHIP_INTERCEPTOR` and `SHIP_EXPLORER`.

I saved the detail from the shipyard below for future reference, as this data is not captured in the DB yet - capturing price information should be a priority for early on in week 5 before we start exploring. I note that whilst the explorer is impressive, the command ship is equally as fast and only the 300 extra fuel capacity is noteworthy. 


We also succeeded in getting the package to build - an important milestone for building additional projects. Currently the conductor/dispatcher project could be moved into its own repository, but I'm happy with not doing that.

Our testing coverage has also decreased relative to the scale of the project, which is unfortunate.

For week 5 I'd like to see the following:
* Exploration script can handle multi-jumps to get between systems
* Conductor decides when mixed vessels should survey or mine
* Unified handling of contracts (Cross agent collaboration)

Some problems I think we still need to solve:
* the tanking price of materials in the starting system - Once prices reach a suitably low point, can get start a multi-system supply chain at more profitable locations?



```json
{
  "data": {
    "symbol": "X1-SZ47-85403Z",
    "shipTypes": [
      {
        "type": "SHIP_LIGHT_HAULER"
      },
      {
        "type": "SHIP_INTERCEPTOR"
      },
      {
        "type": "SHIP_EXPLORER"
      }
    ],
    "transactions": [],
    "ships": [
      {
        "type": "SHIP_LIGHT_HAULER",
        "name": "Light Hauler",
        "description": "A small, fast cargo ship that is designed for short-range transport of light loads.",
        "purchasePrice": 331934,
        "frame": {
          "symbol": "FRAME_LIGHT_FREIGHTER",
          "name": "Frame Light Freighter",
          "description": "A small, versatile spacecraft used for cargo transport and other commercial operations.",
          "moduleSlots": 6,
          "mountingPoints": 1,
          "fuelCapacity": 1700,
          "requirements": {
            "power": 5,
            "crew": 40
          }
        },
        "reactor": {
          "symbol": "REACTOR_CHEMICAL_I",
          "name": "Chemical Reactor I",
          "description": "A basic chemical power reactor, used to generate electricity from chemical reactions.",
          "powerOutput": 15,
          "requirements": {
            "crew": 3
          }
        },
        "engine": {
          "symbol": "ENGINE_ION_DRIVE_I",
          "name": "Ion Drive I",
          "description": "An advanced propulsion system that uses ionized particles to generate high-speed, low-thrust acceleration.",
          "speed": 10,
          "requirements": {
            "power": 3,
            "crew": 3
          }
        },
        "modules": [
          {
            "symbol": "MODULE_CARGO_HOLD_I",
            "name": "Cargo Hold",
            "description": "A module that increases a ship's cargo capacity.",
            "capacity": 30,
            "requirements": {
              "crew": 0,
              "power": 1,
              "slots": 1
            }
          },
          {
            "symbol": "MODULE_CARGO_HOLD_I",
            "name": "Cargo Hold",
            "description": "A module that increases a ship's cargo capacity.",
            "capacity": 30,
            "requirements": {
              "crew": 0,
              "power": 1,
              "slots": 1
            }
          },
          {
            "symbol": "MODULE_CARGO_HOLD_I",
            "name": "Cargo Hold",
            "description": "A module that increases a ship's cargo capacity.",
            "capacity": 30,
            "requirements": {
              "crew": 0,
              "power": 1,
              "slots": 1
            }
          },
          {
            "symbol": "MODULE_CARGO_HOLD_I",
            "name": "Cargo Hold",
            "description": "A module that increases a ship's cargo capacity.",
            "capacity": 30,
            "requirements": {
              "crew": 0,
              "power": 1,
              "slots": 1
            }
          },
          {
            "symbol": "MODULE_CREW_QUARTERS_I",
            "name": "Crew Quarters",
            "description": "A module that provides living space and amenities for the crew.",
            "capacity": 40,
            "requirements": {
              "crew": 2,
              "power": 1,
              "slots": 1
            }
          },
          {
            "symbol": "MODULE_CREW_QUARTERS_I",
            "name": "Crew Quarters",
            "description": "A module that provides living space and amenities for the crew.",
            "capacity": 40,
            "requirements": {
              "crew": 2,
              "power": 1,
              "slots": 1
            }
          }
        ],
        "mounts": [
          {
            "symbol": "MOUNT_SURVEYOR_I",
            "name": "Surveyor I",
            "description": "A basic survey probe that can be used to gather information about a mineral deposit.",
            "strength": 1,
            "deposits": [
              "QUARTZ_SAND",
              "SILICON_CRYSTALS",
              "PRECIOUS_STONES",
              "ICE_WATER",
              "AMMONIA_ICE",
              "IRON_ORE",
              "COPPER_ORE",
              "SILVER_ORE",
              "ALUMINUM_ORE",
              "GOLD_ORE",
              "PLATINUM_ORE"
            ],
            "requirements": {
              "crew": 2,
              "power": 1
            }
          }
        ]
      },
      {
        "type": "SHIP_INTERCEPTOR",
        "name": "Interceptor",
        "description": "A small, agile spacecraft designed for high-speed, short-range combat missions.",
        "purchasePrice": 100940,
        "frame": {
          "symbol": "FRAME_INTERCEPTOR",
          "name": "Frame Interceptor",
          "description": "A small, agile spacecraft designed for high-speed, short-range combat missions.",
          "moduleSlots": 2,
          "mountingPoints": 2,
          "fuelCapacity": 500,
          "requirements": {
            "power": 1,
            "crew": 5
          }
        },
        "reactor": {
          "symbol": "REACTOR_CHEMICAL_I",
          "name": "Chemical Reactor I",
          "description": "A basic chemical power reactor, used to generate electricity from chemical reactions.",
          "powerOutput": 15,
          "requirements": {
            "crew": 3
          }
        },
        "engine": {
          "symbol": "ENGINE_ION_DRIVE_I",
          "name": "Ion Drive I",
          "description": "An advanced propulsion system that uses ionized particles to generate high-speed, low-thrust acceleration.",
          "speed": 10,
          "requirements": {
            "power": 3,
            "crew": 3
          }
        },
        "modules": [
          {
            "symbol": "MODULE_CREW_QUARTERS_I",
            "name": "Crew Quarters",
            "description": "A module that provides living space and amenities for the crew.",
            "capacity": 40,
            "requirements": {
              "crew": 2,
              "power": 1,
              "slots": 1
            }
          }
        ],
        "mounts": [
          {
            "symbol": "MOUNT_TURRET_I",
            "name": "Rotary Cannon",
            "description": "A rotary cannon is a type of mounted turret that is designed to fire a high volume of rounds in rapid succession.",
            "requirements": {
              "power": 1,
              "crew": 1
            }
          },
          {
            "symbol": "MOUNT_MISSILE_LAUNCHER_I",
            "name": "Missile Launcher",
            "description": "A basic missile launcher that fires guided missiles with a variety of warheads for different targets.",
            "requirements": {
              "power": 1,
              "crew": 2
            }
          }
        ]
      },
      {
        "type": "SHIP_EXPLORER",
        "name": "Explorer",
        "description": "A large, long-range spacecraft designed for deep space exploration and scientific research.",
        "purchasePrice": 446400,
        "frame": {
          "symbol": "FRAME_EXPLORER",
          "name": "Frame Explorer",
          "description": "A large, long-range spacecraft designed for deep space exploration and scientific research.",
          "moduleSlots": 8,
          "mountingPoints": 2,
          "fuelCapacity": 1500,
          "requirements": {
            "power": 5,
            "crew": 30
          }
        },
        "reactor": {
          "symbol": "REACTOR_FUSION_I",
          "name": "Fusion Reactor I",
          "description": "A basic fusion power reactor, used to generate electricity from nuclear fusion reactions.",
          "powerOutput": 40,
          "requirements": {
            "crew": 12
          }
        },
        "engine": {
          "symbol": "ENGINE_ION_DRIVE_II",
          "name": "Ion Drive II",
          "description": "An advanced propulsion system that uses ionized particles to generate high-speed, low-thrust acceleration, with improved efficiency and performance.",
          "speed": 30,
          "requirements": {
            "power": 6,
            "crew": 8
          }
        },
        "modules": [
          {
            "symbol": "MODULE_CARGO_HOLD_I",
            "name": "Cargo Hold",
            "description": "A module that increases a ship's cargo capacity.",
            "capacity": 30,
            "requirements": {
              "crew": 0,
              "power": 1,
              "slots": 1
            }
          },
          {
            "symbol": "MODULE_CREW_QUARTERS_I",
            "name": "Crew Quarters",
            "description": "A module that provides living space and amenities for the crew.",
            "capacity": 40,
            "requirements": {
              "crew": 2,
              "power": 1,
              "slots": 1
            }
          },
          {
            "symbol": "MODULE_CREW_QUARTERS_I",
            "name": "Crew Quarters",
            "description": "A module that provides living space and amenities for the crew.",
            "capacity": 40,
            "requirements": {
              "crew": 2,
              "power": 1,
              "slots": 1
            }
          },
          {
            "symbol": "MODULE_SCIENCE_LAB_I",
            "name": "Science Lab",
            "description": "A specialized module equipped with advanced instruments and equipment for scientific research and analysis.",
            "requirements": {
              "crew": 6,
              "power": 2,
              "slots": 2
            }
          },
          {
            "symbol": "MODULE_WARP_DRIVE_I",
            "name": "Warp Drive I",
            "description": "A basic warp drive that allows for short-range interstellar travel.",
            "range": 2000,
            "requirements": {
              "crew": 2,
              "power": 3,
              "slots": 1
            }
          },
          {
            "symbol": "MODULE_SHIELD_GENERATOR_I",
            "name": "Shield Generator",
            "description": "A basic shield generator that provides protection against incoming weapons fire and other hazards.",
            "requirements": {
              "crew": 2,
              "power": 3,
              "slots": 1
            }
          }
        ],
        "mounts": [
          {
            "symbol": "MOUNT_SENSOR_ARRAY_II",
            "name": "Sensor Array II",
            "description": "An advanced sensor array that improves a ship's ability to detect and track other objects in space with greater accuracy and range.",
            "strength": 4,
            "requirements": {
              "crew": 2,
              "power": 2
            }
          },
          {
            "symbol": "MOUNT_LASER_CANNON_I",
            "name": "Laser Cannon",
            "description": "A basic laser weapon that fires concentrated beams of energy at high speed and accuracy.",
            "requirements": {
              "power": 2,
              "crew": 1
            }
          }
        ]
      }
    ]
  }
}


```