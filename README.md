
# Executive Summary

SpaceTraders.io is a headless game that is played via executing commands via the Rest API.  
This project contains a series `behaviours` - a set of instructions that a ship follows.  

The project also contains a `dispatcher` which based on values in a configured data


[![PyTest](https://github.com/Ctri-The-Third/SpaceTraders/actions/workflows/main.yml/badge.svg)](https://github.com/Ctri-The-Third/SpaceTraders/actions/workflows/main.yml)

- [Overview](#Overview)
- [Environment setup](#Setup)
- [Deployment](#Deploy)


## Overview

* `dispatcherWK25.py` - takes a user token from the user.json configuration file (or tries to register a user if one is not found)    
dispatcher reads the database for behaviours and 1-off tasks and executes matching `behaviours`   
* `conductorWK25.py` - assigns behaviours to ships based on the contents of a custom game plan file like or populates its own default game plan.
* `behaviours\` is a folder of python classes that inherit `generic_behaviour.py`. They all execute and initialise in the same way, and can be run from command line, or automatically the dispatcher.  
