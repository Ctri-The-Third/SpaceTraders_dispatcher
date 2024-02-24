
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



## Setup

You need to set the following environment variables:

If you wanted to use a .env file, you could use the following format:

```bash
ST_TOKEN=eyJh....
ST_DB_HOST=spacetraders_db_instance
ST_DB_PASSWORD=spacetraders_pass
ST_DB_NAME=spacetraders
ST_DB_PORT=5432
POSTGRES_PASSWORD=spacetraders_pass 
```

## Deploy

You can use docker-compose to deploy the application.

```bash
docker compose  -f "scripts\all_in_one_compose.yml" up -d 
```

This will host the UI on port 3000, the DB on port 5432, and execute the dispatcher application with whatever token is specified in the .env file.