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

--
-- PostgreSQL database dump
--

-- Dumped from database version 15.3
-- Dumped by pg_dump version 15.3

-- Started on 2023-07-20 00:30:28

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 217 (class 1259 OID 16453)
-- Name: market; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.market (
    symbol text NOT NULL,
    system_symbol text
);


ALTER TABLE public.market OWNER TO spacetraders;

--
-- TOC entry 218 (class 1259 OID 16460)
-- Name: market_tradegood; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.market_tradegood (
    market_waypoint text NOT NULL,
    symbol text NOT NULL,
    buy_or_sell text,
    name text,
    description text
);


ALTER TABLE public.market_tradegood OWNER TO spacetraders;

--
-- TOC entry 219 (class 1259 OID 16467)
-- Name: market_tradegood_listing; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.market_tradegood_listing (
    market_symbol text NOT NULL,
    symbol text NOT NULL,
    supply text,
    purchase_price integer,
    sell_price integer,
    last_updated timestamp without time zone
);


ALTER TABLE public.market_tradegood_listing OWNER TO spacetraders;

--
-- TOC entry 220 (class 1259 OID 16474)
-- Name: shipyard_types; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.shipyard_types (
    shipyard_symbol text NOT NULL,
    ship_type text NOT NULL
);


ALTER TABLE public.shipyard_types OWNER TO spacetraders;

--
-- TOC entry 214 (class 1259 OID 16436)
-- Name: test; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.test (
);


ALTER TABLE public.test OWNER TO postgres;

--
-- TOC entry 216 (class 1259 OID 16446)
-- Name: waypoint_traits; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.waypoint_traits (
    waypoint text NOT NULL,
    symbol text NOT NULL,
    name text,
    description text
);


ALTER TABLE public.waypoint_traits OWNER TO spacetraders;

--
-- TOC entry 215 (class 1259 OID 16439)
-- Name: waypoints; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.waypoints (
    symbol text NOT NULL,
    type text NOT NULL,
    system_symbol text NOT NULL,
    x smallint NOT NULL,
    y smallint NOT NULL
);


ALTER TABLE public.waypoints OWNER TO spacetraders;

--
-- TOC entry 3201 (class 2606 OID 16459)
-- Name: market market_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.market
    ADD CONSTRAINT market_pkey PRIMARY KEY (symbol);


--
-- TOC entry 3203 (class 2606 OID 16466)
-- Name: market_tradegood market_tradegood_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.market_tradegood
    ADD CONSTRAINT market_tradegood_pkey PRIMARY KEY (market_waypoint, symbol);


--
-- TOC entry 3207 (class 2606 OID 16480)
-- Name: shipyard_types shipyard_types_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.shipyard_types
    ADD CONSTRAINT shipyard_types_pkey PRIMARY KEY (shipyard_symbol, ship_type);


--
-- TOC entry 3205 (class 2606 OID 16473)
-- Name: market_tradegood_listing tradegoods_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.market_tradegood_listing
    ADD CONSTRAINT tradegoods_pkey PRIMARY KEY (market_symbol, symbol);


--
-- TOC entry 3197 (class 2606 OID 16445)
-- Name: waypoints waypoint_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.waypoints
    ADD CONSTRAINT waypoint_pkey PRIMARY KEY (symbol);


--
-- TOC entry 3199 (class 2606 OID 16452)
-- Name: waypoint_traits waypoint_traits_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.waypoint_traits
    ADD CONSTRAINT waypoint_traits_pkey PRIMARY KEY (waypoint, symbol);


--
-- TOC entry 3355 (class 0 OID 0)
-- Dependencies: 5
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: pg_database_owner
--

REVOKE USAGE ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO PUBLIC;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO spacetraders;


-- Completed on 2023-07-20 00:30:28

--
-- PostgreSQL database dump complete
--

