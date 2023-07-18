-- dumped straight out of Postgres. NOTE THE GRANTS & table ownership.
CREATE ROLE spacetraders LOGIN PASSWORD 'spacetraders' NOINHERIT CREATEDB;-- SCHEMA: public

-- DROP SCHEMA IF EXISTS public ;

-- Database: spacetraders

-- DROP DATABASE IF EXISTS spacetraders;

CREATE DATABASE spacetraders
    WITH
    OWNER = spacetraders
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_GB.UTF-8'
    LC_CTYPE = 'en_GB.UTF-8'
    TABLESPACE = pg_default
    CONNECTION LIMIT = -1
    IS_TEMPLATE = False;


\c spacetraders;
--SET search_path TO spacetraders;

CREATE SCHEMA IF NOT EXISTS public
    AUTHORIZATION postgres;

COMMENT ON SCHEMA public
    IS 'standard public schema';

GRANT ALL ON SCHEMA public TO PUBLIC;

GRANT ALL ON SCHEMA public TO postgres;

GRANT ALL ON SCHEMA public TO spacetraders;


-- Table: public.waypoints

-- DROP TABLE IF EXISTS public.waypoints;

CREATE TABLE IF NOT EXISTS public.waypoints
(
    symbol text COLLATE pg_catalog."default" NOT NULL,
    type text COLLATE pg_catalog."default" NOT NULL,
    system_symbol text COLLATE pg_catalog."default" NOT NULL,
    x smallint NOT NULL,
    y smallint NOT NULL,
    CONSTRAINT waypoint_pkey PRIMARY KEY (symbol)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.waypoints
    OWNER to spacetraders;

REVOKE ALL ON TABLE public.waypoints FROM spacetraders;

GRANT ALL ON TABLE public.waypoints to spacetraders;

GRANT DELETE, UPDATE, INSERT, SELECT ON TABLE public.waypoints TO spacetraders;


-- Table: public.waypoint_traits

-- DROP TABLE IF EXISTS public.waypoint_traits;

CREATE TABLE IF NOT EXISTS public.waypoint_traits
(
    waypoint text COLLATE pg_catalog."default" NOT NULL,
    symbol text COLLATE pg_catalog."default" NOT NULL,
    name text COLLATE pg_catalog."default",
    description text COLLATE pg_catalog."default",
    CONSTRAINT waypoint_traits_pkey PRIMARY KEY (waypoint, symbol)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.waypoint_traits
    OWNER to spacetraders;

REVOKE ALL ON TABLE public.waypoint_traits FROM spacetraders;

GRANT ALL ON TABLE public.waypoint_traits to spacetraders;

GRANT DELETE, UPDATE, INSERT, SELECT ON TABLE public.waypoint_traits TO spacetraders;

-- Table: public.market

-- DROP TABLE IF EXISTS public.market;

CREATE TABLE IF NOT EXISTS public.market
(
    symbol text COLLATE pg_catalog."default" NOT NULL,
    CONSTRAINT market_pkey PRIMARY KEY (symbol)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.market
    OWNER to spacetraders;


    -- Table: public.market_tradegood

-- DROP TABLE IF EXISTS public.market_tradegood;

CREATE TABLE IF NOT EXISTS public.market_tradegood
(
    market_waypoint text COLLATE pg_catalog."default" NOT NULL,
    symbol text COLLATE pg_catalog."default" NOT NULL,
    buy_or_sell text COLLATE pg_catalog."default",
    name text COLLATE pg_catalog."default",
    description text COLLATE pg_catalog."default",
    CONSTRAINT market_tradegood_pkey PRIMARY KEY (market_waypoint, symbol)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.market_tradegood
    OWNER to spacetraders;

-- Table: public.market_tradegood_detail

-- DROP TABLE IF EXISTS public.market_tradegood_detail;

CREATE TABLE IF NOT EXISTS public.market_tradegood_detail
(
    market_symbol text COLLATE pg_catalog."default" NOT NULL,
    symbol text COLLATE pg_catalog."default" NOT NULL,
    supply text COLLATE pg_catalog."default",
    purchase_price integer,
    sell_price integer,
    CONSTRAINT tradegoods_pkey PRIMARY KEY (market_symbol, symbol)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.market_tradegood_detail
    OWNER to spacetraders;