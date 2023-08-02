
# Readme outline
Executive Summary

An API wrapper for the [SpaceTraders API](https://spacetraders.io/) written in Python.
Implemented as an object-oriented wrapper around the [requests](https://docs.python-requests.org/en/master/) library.

Reinventing the wheel for fun, and to express recent learnings.

Eventually will be used to build an interactive gameplay UI built on top of the API.

[![PyTest](https://github.com/Ctri-The-Third/SpaceTraders/actions/workflows/main.yml/badge.svg)](https://github.com/Ctri-The-Third/SpaceTraders/actions/workflows/main.yml)

- [Overview](#Overview)
- [Environment setup](#Setup)
- [Deployment](#Deploy)


## Overview
A series of helper classes for interacting with the API.
`client_api` - directly interacts with the API
`client_postgres` - updates info in / fetches info from a configured postgres database instead of bothering the API
`client_pg_logger` - a client that just puts in logs to the postgres database whenever its methods are called (useful for tracking API usage & behaviours efficacy
-`client_stub` - a stub client that just does nothing. 

-✨`client_mediator`✨ - a client that can connect all of the above, checking the DB before bothering the API, feeding API responses into the DB, and logging API calls to the DB.

All the clients implement the same abstract interface, so can be used interchangably (most useful when going from the basic API class to the mediator class / vice versa.)

## Setup

```bash
# build 
py setup.py bdist_wheel

# install
py -m pip install dist/spacetraders-0.4.0-py3-none-any.whl
```

## Usage! 

The package has a number of client classes that can be used to interact with the API. They are intended to be largely interchangable.

Quickstart - API only
```python
from straders_sdk.client_api import SpaceTradersApiClient as SpaceTraders
st = SpaceTraders("")
st.register("SAMPLE_AGENT")
ships = st.ships_view()
    for ship in ships:     
        print (f"{ship.name} is at {ship.nav.waypoint_symbol}")


```