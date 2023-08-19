--psql -U <username> -d <database_name> -f <file_name>.sql

set search_path = public;

-------------------------------------------
--
-- PostgreSQL database dump
--

--
-- PostgreSQL database dump
--

-- Dumped from database version 13.11 (Debian 13.11-0+deb11u1)
-- Dumped by pg_dump version 15.3

-- Started on 2023-08-19 11:41:19

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

--
-- TOC entry 6 (class 2615 OID 2200)
-- Name: public; Type: SCHEMA; Schema: -; Owner: postgres
--

-- *not* creating schema, since initdb creates it


ALTER SCHEMA public OWNER TO postgres;

--
-- TOC entry 2 (class 3079 OID 26914)
-- Name: tablefunc; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS tablefunc WITH SCHEMA public;


--
-- TOC entry 3289 (class 0 OID 0)
-- Dependencies: 2
-- Name: EXTENSION tablefunc; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION tablefunc IS 'functions that manipulate whole tables, including crosstab';


--
-- TOC entry 250 (class 1255 OID 16605)
-- Name: update_last_updated(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_last_updated() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  NEW.last_updated := NOW();
  RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_last_updated() OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 211 (class 1259 OID 16688)
-- Name: agents; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.agents (
    symbol text NOT NULL,
    headquarters text,
    credits integer,
    starting_faction text,
    ship_count integer,
    last_updated timestamp without time zone
);


ALTER TABLE public.agents OWNER TO spacetraders;

--
-- TOC entry 204 (class 1259 OID 16624)
-- Name: ship; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.ship (
    ship_symbol text NOT NULL,
    agent_name text,
    faction_symbol text,
    ship_role text,
    cargo_capacity integer,
    cargo_in_use integer,
    last_updated timestamp without time zone,
    fuel_capacity integer,
    fuel_current integer
);


ALTER TABLE public.ship OWNER TO spacetraders;

--
-- TOC entry 235 (class 1259 OID 26901)
-- Name: transactions; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.transactions (
    waypoint_symbol text,
    ship_symbol text NOT NULL,
    trade_symbol text,
    type text,
    units integer,
    price_per_unit integer,
    total_price numeric,
    session_id text,
    "timestamp" timestamp without time zone NOT NULL
);


ALTER TABLE public.transactions OWNER TO spacetraders;

--
-- TOC entry 239 (class 1259 OID 26945)
-- Name: agent_credits_per_hour; Type: VIEW; Schema: public; Owner: spacetraders
--

CREATE VIEW public.agent_credits_per_hour AS
 WITH data AS (
         SELECT s.agent_name,
            sum(
                CASE
                    WHEN (t.type = 'SELL'::text) THEN t.total_price
                    ELSE NULL::numeric
                END) AS credits_earned,
            date_trunc('hour'::text, t."timestamp") AS event_hour
           FROM ((public.transactions t
             JOIN public.ship s ON ((t.ship_symbol = s.ship_symbol)))
             JOIN public.agents a ON ((s.agent_name = a.symbol)))
          GROUP BY s.agent_name, (date_trunc('hour'::text, t."timestamp"))
        )
 SELECT data.agent_name,
    data.credits_earned,
    data.event_hour
   FROM data;


ALTER TABLE public.agent_credits_per_hour OWNER TO spacetraders;

--
-- TOC entry 217 (class 1259 OID 16820)
-- Name: agent_overview; Type: VIEW; Schema: public; Owner: spacetraders
--

CREATE VIEW public.agent_overview AS
 SELECT a.symbol,
    a.credits,
    a.starting_faction,
    count(DISTINCT s.ship_symbol) AS ship_count,
    a.last_updated
   FROM (public.agents a
     JOIN public.ship s ON ((s.agent_name = a.symbol)))
  GROUP BY a.symbol, a.credits, a.starting_faction, a.last_updated
  ORDER BY a.last_updated DESC;


ALTER TABLE public.agent_overview OWNER TO spacetraders;

--
-- TOC entry 212 (class 1259 OID 16696)
-- Name: logging; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.logging (
    event_name text,
    event_timestamp timestamp without time zone NOT NULL,
    agent_name text,
    ship_name text NOT NULL,
    session_id text,
    endpoint_name text,
    new_credits integer,
    status_code integer,
    error_code integer,
    event_params jsonb
);


ALTER TABLE public.logging OWNER TO spacetraders;

--
-- TOC entry 247 (class 1259 OID 27208)
-- Name: mat_session_stats; Type: MATERIALIZED VIEW; Schema: public; Owner: spacetraders
--

CREATE MATERIALIZED VIEW public.mat_session_stats AS
 WITH sessions_and_requests AS (
         SELECT logging.session_id,
            min(logging.event_timestamp) AS session_start,
            max(logging.event_timestamp) AS session_end,
            count(
                CASE
                    WHEN ((logging.status_code > 0) AND (logging.status_code <> ALL (ARRAY[404, 429, 500]))) THEN 1
                    ELSE NULL::integer
                END) AS requests,
            count(
                CASE
                    WHEN (logging.status_code = 429) THEN 1
                    ELSE NULL::integer
                END) AS delayed_requests
           FROM public.logging
          WHERE (logging.event_timestamp >= (now() - '3 days'::interval))
          GROUP BY logging.session_id
        ), sessions_and_earnings AS (
         SELECT t.session_id,
            sum(t.total_price) AS earnings
           FROM public.transactions t
          WHERE ((t.type = 'SELL'::text) AND (t."timestamp" >= (now() - '3 days'::interval)))
          GROUP BY t.session_id
        ), sessions_and_ship_names AS (
         SELECT DISTINCT logging.ship_name AS ship_symbol,
            logging.session_id
           FROM public.logging
          WHERE (logging.ship_name <> 'GLOBAL'::text)
        )
 SELECT sas.ship_symbol,
    sar.session_start,
    sar.session_id,
    COALESCE(ear.earnings, (0)::numeric) AS earnings,
    sar.requests,
    sar.delayed_requests,
    (COALESCE(ear.earnings, (0)::numeric) / (
        CASE
            WHEN (sar.requests = 0) THEN (1)::bigint
            ELSE sar.requests
        END)::numeric) AS cpr
   FROM ((sessions_and_requests sar
     LEFT JOIN sessions_and_earnings ear ON ((ear.session_id = sar.session_id)))
     LEFT JOIN sessions_and_ship_names sas ON ((sar.session_id = sas.session_id)))
  ORDER BY sar.session_start DESC
  WITH NO DATA;


ALTER TABLE public.mat_session_stats OWNER TO spacetraders;

--
-- TOC entry 214 (class 1259 OID 16712)
-- Name: ship_behaviours; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.ship_behaviours (
    ship_symbol text NOT NULL,
    behaviour_id text,
    locked_by text,
    locked_until timestamp without time zone,
    behaviour_params jsonb
);


ALTER TABLE public.ship_behaviours OWNER TO spacetraders;

--
-- TOC entry 248 (class 1259 OID 27221)
-- Name: behaviour_performance; Type: VIEW; Schema: public; Owner: spacetraders
--

CREATE VIEW public.behaviour_performance AS
 WITH data AS (
         SELECT date_trunc('hour'::text, mss.session_start) AS activity_window,
            s.ship_symbol,
            s.ship_role,
            sb.behaviour_id,
            sum(mss.earnings) AS earnings,
            sum(mss.requests) AS requests,
            count(*) AS sessions
           FROM ((public.mat_session_stats mss
             JOIN public.ship s ON ((mss.ship_symbol = s.ship_symbol)))
             JOIN public.ship_behaviours sb ON ((s.ship_symbol = sb.ship_symbol)))
          WHERE ((mss.session_start < date_trunc('hour'::text, now())) AND (mss.session_start >= (now() - '1 day'::interval)))
          GROUP BY (date_trunc('hour'::text, mss.session_start)), s.ship_symbol, s.ship_role, sb.behaviour_id
          ORDER BY (date_trunc('hour'::text, mss.session_start)) DESC, s.ship_symbol
        ), data_2 AS (
         SELECT data.activity_window,
            data.behaviour_id,
            sum(data.sessions) AS sessions,
            sum(data.earnings) AS earnings,
            sum(data.requests) AS requests,
            round((sum(data.earnings) / sum(data.requests)), 2) AS cpr,
            round((sum(data.earnings) / sum(data.sessions)), 2) AS bhvr_cph
           FROM data
          GROUP BY data.activity_window, data.behaviour_id
          ORDER BY data.activity_window DESC
        )
 SELECT data_2.activity_window,
    data_2.behaviour_id,
    data_2.sessions,
    data_2.earnings,
    data_2.requests,
    data_2.cpr,
    data_2.bhvr_cph
   FROM data_2
  WHERE (data_2.earnings > (0)::numeric);


ALTER TABLE public.behaviour_performance OWNER TO spacetraders;

--
-- TOC entry 219 (class 1259 OID 16896)
-- Name: contract_tradegoods; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.contract_tradegoods (
    contract_id text NOT NULL,
    trade_symbol text NOT NULL,
    destination_symbol text,
    units_required integer,
    units_fulfilled integer
);


ALTER TABLE public.contract_tradegoods OWNER TO spacetraders;

--
-- TOC entry 218 (class 1259 OID 16886)
-- Name: contracts; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.contracts (
    id text NOT NULL,
    faction_symbol text,
    type text,
    accepted boolean,
    fulfilled boolean,
    expiration timestamp without time zone,
    deadline timestamp without time zone,
    agent_symbol text,
    payment_upfront integer,
    payment_on_completion integer
);


ALTER TABLE public.contracts OWNER TO spacetraders;

--
-- TOC entry 233 (class 1259 OID 18289)
-- Name: contracts_overview; Type: VIEW; Schema: public; Owner: spacetraders
--

CREATE VIEW public.contracts_overview AS
 SELECT co.agent_symbol,
    ct.trade_symbol,
    round((((ct.units_fulfilled)::numeric / (ct.units_required)::numeric) * (100)::numeric), 2) AS progress,
    ct.units_required,
    ct.units_fulfilled,
    co.expiration,
    (co.payment_on_completion / ct.units_required) AS payment_per_item,
    co.fulfilled
   FROM (public.contracts co
     JOIN public.contract_tradegoods ct ON ((co.id = ct.contract_id)));


ALTER TABLE public.contracts_overview OWNER TO spacetraders;

--
-- TOC entry 226 (class 1259 OID 17758)
-- Name: jump_gates; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.jump_gates (
    waypoint_symbol text NOT NULL,
    faction_symbol text,
    jump_range integer
);


ALTER TABLE public.jump_gates OWNER TO spacetraders;

--
-- TOC entry 227 (class 1259 OID 17766)
-- Name: jumpgate_connections; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.jumpgate_connections (
    source_waypoint text NOT NULL,
    destination_waypoint text NOT NULL,
    distance integer
);


ALTER TABLE public.jumpgate_connections OWNER TO spacetraders;

--
-- TOC entry 234 (class 1259 OID 18361)
-- Name: waypoint_charts; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.waypoint_charts (
    waypoint_symbol text NOT NULL,
    submitted_by text NOT NULL,
    submitted_on timestamp without time zone NOT NULL
);


ALTER TABLE public.waypoint_charts OWNER TO spacetraders;

--
-- TOC entry 208 (class 1259 OID 16648)
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
-- TOC entry 209 (class 1259 OID 16654)
-- Name: waypoints; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.waypoints (
    symbol text NOT NULL,
    type text NOT NULL,
    system_symbol text NOT NULL,
    x smallint NOT NULL,
    y smallint NOT NULL,
    checked boolean DEFAULT false NOT NULL
);


ALTER TABLE public.waypoints OWNER TO spacetraders;

--
-- TOC entry 242 (class 1259 OID 27010)
-- Name: jumpgates_scanned; Type: VIEW; Schema: public; Owner: spacetraders
--

CREATE VIEW public.jumpgates_scanned AS
 SELECT w.symbol AS waypoint_symbol,
    (count(
        CASE
            WHEN (wt.symbol = 'UNCHARTED'::text) THEN 1
            ELSE NULL::integer
        END) > 0) AS uncharted,
    (count(
        CASE
            WHEN (wc.waypoint_symbol IS NOT NULL) THEN 1
            ELSE NULL::integer
        END) > 0) AS charted,
    (count(
        CASE
            WHEN (jg.waypoint_symbol IS NOT NULL) THEN 1
            ELSE NULL::integer
        END) > 0) AS scanned
   FROM (((public.waypoints w
     LEFT JOIN public.waypoint_traits wt ON ((wt.waypoint = w.symbol)))
     LEFT JOIN public.waypoint_charts wc ON ((wc.waypoint_symbol = w.symbol)))
     LEFT JOIN public.jump_gates jg ON ((jg.waypoint_symbol = w.symbol)))
  WHERE (w.type = 'JUMP_GATE'::text)
  GROUP BY w.symbol;


ALTER TABLE public.jumpgates_scanned OWNER TO spacetraders;

--
-- TOC entry 243 (class 1259 OID 27016)
-- Name: jumpgates_scanned_progress; Type: VIEW; Schema: public; Owner: spacetraders
--

CREATE VIEW public.jumpgates_scanned_progress AS
 WITH data AS (
         SELECT count(*) AS total_gates,
            count(
                CASE
                    WHEN js.scanned THEN 1
                    ELSE NULL::integer
                END) AS scanned_gates,
            count(
                CASE
                    WHEN js.charted THEN 1
                    ELSE NULL::integer
                END) AS charted_gates
           FROM public.jumpgates_scanned js
        )
 SELECT 'charted jumpgates scanned'::text AS title,
    data.scanned_gates,
    data.charted_gates,
    round((((data.charted_gates)::numeric / (data.scanned_gates)::numeric) * (100)::numeric), 2) AS progress
   FROM data;


ALTER TABLE public.jumpgates_scanned_progress OWNER TO spacetraders;

--
-- TOC entry 201 (class 1259 OID 16606)
-- Name: market; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.market (
    symbol text NOT NULL,
    system_symbol text
);


ALTER TABLE public.market OWNER TO spacetraders;

--
-- TOC entry 203 (class 1259 OID 16618)
-- Name: market_tradegood_listing; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.market_tradegood_listing (
    market_symbol text NOT NULL,
    symbol text NOT NULL,
    supply text,
    purchase_price integer,
    sell_price integer,
    last_updated timestamp without time zone,
    market_depth integer
);


ALTER TABLE public.market_tradegood_listing OWNER TO spacetraders;

--
-- TOC entry 220 (class 1259 OID 17106)
-- Name: market_prices; Type: VIEW; Schema: public; Owner: spacetraders
--

CREATE VIEW public.market_prices AS
 SELECT market_tradegood_listing.symbol,
    round(avg(market_tradegood_listing.purchase_price)) AS buy_price,
    round(avg(market_tradegood_listing.sell_price)) AS sell_price,
    count(*) AS sources
   FROM public.market_tradegood_listing
  GROUP BY market_tradegood_listing.symbol
  ORDER BY market_tradegood_listing.symbol;


ALTER TABLE public.market_prices OWNER TO spacetraders;

--
-- TOC entry 202 (class 1259 OID 16612)
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
-- TOC entry 244 (class 1259 OID 27097)
-- Name: mat_shipyardtypes_to_ship; Type: MATERIALIZED VIEW; Schema: public; Owner: spacetraders
--

CREATE MATERIALIZED VIEW public.mat_shipyardtypes_to_ship AS
 SELECT unnest(ARRAY['HAULERFRAME_LIGHT_FREIGHTER'::text, 'EXCAVATORFRAME_MINER'::text, 'COMMANDFRAME_FRIGATE'::text, 'EXCAVATORFRAME_DRONE'::text]) AS ship_roleframe,
    unnest(ARRAY['SHIP_LIGHT_FREIGHTER'::text, 'SHIP_ORE_HOUND'::text, 'SHIP_COMMAND_FRIGATE'::text, 'SHIP_MINING_DRONE'::text]) AS shipyard_type
  WITH NO DATA;


ALTER TABLE public.mat_shipyardtypes_to_ship OWNER TO spacetraders;

--
-- TOC entry 206 (class 1259 OID 16636)
-- Name: shipyard_types; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.shipyard_types (
    shipyard_symbol text NOT NULL,
    ship_type text NOT NULL,
    ship_cost integer,
    last_updated timestamp without time zone
);


ALTER TABLE public.shipyard_types OWNER TO spacetraders;

--
-- TOC entry 207 (class 1259 OID 16642)
-- Name: systems; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.systems (
    symbol text NOT NULL,
    sector_symbol text,
    type text,
    x integer,
    y integer
);


ALTER TABLE public.systems OWNER TO spacetraders;

--
-- TOC entry 225 (class 1259 OID 17747)
-- Name: mkt_shpyrds_systems_last_updated; Type: VIEW; Schema: public; Owner: spacetraders
--

CREATE VIEW public.mkt_shpyrds_systems_last_updated AS
 SELECT wt.waypoint,
    s.x,
    s.y,
    min(COALESCE(mtl.last_updated, st.last_updated, '1990-01-01 00:00:00'::timestamp without time zone)) AS last_updated
   FROM ((((public.waypoint_traits wt
     JOIN public.waypoints w ON ((w.symbol = wt.waypoint)))
     JOIN public.systems s ON ((s.symbol = w.system_symbol)))
     LEFT JOIN public.market_tradegood_listing mtl ON ((mtl.market_symbol = wt.waypoint)))
     LEFT JOIN public.shipyard_types st ON ((st.shipyard_symbol = w.symbol)))
  WHERE (wt.symbol = ANY (ARRAY['MARKETPLACE'::text, 'SHIPYARD'::text]))
  GROUP BY wt.waypoint, s.x, s.y;


ALTER TABLE public.mkt_shpyrds_systems_last_updated OWNER TO spacetraders;

--
-- TOC entry 230 (class 1259 OID 18096)
-- Name: mkt_shpyrds_systems_last_updated_jumpgates; Type: VIEW; Schema: public; Owner: spacetraders
--

CREATE VIEW public.mkt_shpyrds_systems_last_updated_jumpgates AS
 SELECT w1.symbol,
    msslu.x,
    msslu.y,
    msslu.last_updated,
    w2.symbol AS jump_gate_waypoint
   FROM (((public.mkt_shpyrds_systems_last_updated msslu
     JOIN public.waypoints w1 ON ((w1.symbol = msslu.waypoint)))
     JOIN public.waypoints w2 ON ((w1.system_symbol = w2.system_symbol)))
     JOIN public.jump_gates j ON ((w2.symbol = j.waypoint_symbol)))
  WHERE ((w2.type = 'JUMP_GATE'::text) AND (w1.symbol <> w2.symbol));


ALTER TABLE public.mkt_shpyrds_systems_last_updated_jumpgates OWNER TO spacetraders;

--
-- TOC entry 232 (class 1259 OID 18279)
-- Name: mkt_shpyrds_systems_visit_progress; Type: VIEW; Schema: public; Owner: spacetraders
--

CREATE VIEW public.mkt_shpyrds_systems_visit_progress AS
 WITH info AS (
         SELECT count(*) AS total,
            count(
                CASE
                    WHEN (mkt_shpyrds_systems_last_updated_jumpgates.last_updated > '1990-01-01 00:00:00'::timestamp without time zone) THEN 1
                    ELSE NULL::integer
                END) AS visited
           FROM public.mkt_shpyrds_systems_last_updated_jumpgates
        )
 SELECT 'Markets/Shipyards on gate network visited'::text AS "?column?",
    info.visited,
    info.total,
    round((((info.visited)::numeric / (info.total)::numeric) * (100)::numeric), 2) AS progress
   FROM info;


ALTER TABLE public.mkt_shpyrds_systems_visit_progress OWNER TO spacetraders;

--
-- TOC entry 240 (class 1259 OID 26999)
-- Name: mkt_shpyrds_waypoints_scanned; Type: VIEW; Schema: public; Owner: spacetraders
--

CREATE VIEW public.mkt_shpyrds_waypoints_scanned AS
 WITH data AS (
         SELECT wt.waypoint AS waypoint_symbol,
            wt.symbol,
            count(st.*) AS ships_available,
            count(mt.*) AS goods_available
           FROM (((((public.waypoint_traits wt
             JOIN public.waypoints w1 ON ((wt.waypoint = w1.symbol)))
             JOIN public.waypoints w2 ON (((w1.system_symbol = w2.system_symbol) AND (w1.symbol <> w2.symbol))))
             JOIN public.jump_gates jg ON ((jg.waypoint_symbol = w2.symbol)))
             LEFT JOIN public.shipyard_types st ON ((st.shipyard_symbol = w1.symbol)))
             LEFT JOIN public.market_tradegood mt ON ((mt.market_waypoint = w1.symbol)))
          WHERE (wt.symbol = ANY (ARRAY['MARKETPLACE'::text, 'SHIPYARD'::text]))
          GROUP BY wt.waypoint, wt.symbol
        )
 SELECT data.waypoint_symbol,
    ((data.ships_available > 0) OR (data.goods_available > 0)) AS scanned
   FROM data;


ALTER TABLE public.mkt_shpyrds_waypoints_scanned OWNER TO spacetraders;

--
-- TOC entry 241 (class 1259 OID 27004)
-- Name: mkt_shpyrds_waypoints_scanned_progress; Type: VIEW; Schema: public; Owner: spacetraders
--

CREATE VIEW public.mkt_shpyrds_waypoints_scanned_progress AS
 SELECT 'Markets/ shipyards on gate network scanned'::text AS "?column?",
    count(
        CASE
            WHEN mkt_shpyrds_waypoints_scanned.scanned THEN 1
            ELSE NULL::integer
        END) AS scanned,
    count(*) AS total,
    round((((count(
        CASE
            WHEN mkt_shpyrds_waypoints_scanned.scanned THEN 1
            ELSE NULL::integer
        END))::numeric / (count(*))::numeric) * (100)::numeric), 2) AS progress
   FROM public.mkt_shpyrds_waypoints_scanned;


ALTER TABLE public.mkt_shpyrds_waypoints_scanned_progress OWNER TO spacetraders;

--
-- TOC entry 249 (class 1259 OID 27231)
-- Name: session_stats_per_hour; Type: VIEW; Schema: public; Owner: spacetraders
--

CREATE VIEW public.session_stats_per_hour AS
 SELECT s.agent_name,
    date_trunc('hour'::text, mss.session_start) AS activity_time,
    sum(mss.earnings) AS earnings,
    sum(mss.requests) AS requests,
    sum(mss.delayed_requests) AS delayed_requests,
    round((sum(mss.earnings) / sum(mss.requests)), 2) AS cpr
   FROM (public.mat_session_stats mss
     JOIN public.ship s ON ((mss.ship_symbol = s.ship_symbol)))
  WHERE ((mss.session_start < date_trunc('hour'::text, timezone('utc'::text, now()))) AND (date_trunc('hour'::text, mss.session_start) > (now() - '06:00:00'::interval)))
  GROUP BY s.agent_name, (date_trunc('hour'::text, mss.session_start))
  ORDER BY (date_trunc('hour'::text, mss.session_start)) DESC, s.agent_name;


ALTER TABLE public.session_stats_per_hour OWNER TO spacetraders;

--
-- TOC entry 228 (class 1259 OID 18056)
-- Name: ship_cooldowns; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.ship_cooldowns (
    ship_symbol text NOT NULL,
    total_seconds integer,
    expiration timestamp without time zone NOT NULL
);


ALTER TABLE public.ship_cooldowns OWNER TO spacetraders;

--
-- TOC entry 229 (class 1259 OID 18069)
-- Name: ship_cooldown; Type: VIEW; Schema: public; Owner: spacetraders
--

CREATE VIEW public.ship_cooldown AS
 WITH maxes AS (
         SELECT ship_cooldowns.ship_symbol,
            max(ship_cooldowns.expiration) AS expiration
           FROM public.ship_cooldowns
          GROUP BY ship_cooldowns.ship_symbol
        )
 SELECT sc.ship_symbol,
    sc.total_seconds,
    sc.expiration
   FROM (maxes m
     JOIN public.ship_cooldowns sc ON (((m.ship_symbol = sc.ship_symbol) AND (m.expiration = sc.expiration))));


ALTER TABLE public.ship_cooldown OWNER TO spacetraders;

--
-- TOC entry 213 (class 1259 OID 16704)
-- Name: ship_frame_links; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.ship_frame_links (
    ship_symbol text NOT NULL,
    frame_symbol text NOT NULL,
    condition integer
);


ALTER TABLE public.ship_frame_links OWNER TO spacetraders;

--
-- TOC entry 210 (class 1259 OID 16660)
-- Name: ship_frames; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.ship_frames (
    frame_symbol text NOT NULL,
    name text,
    description text,
    module_slots integer,
    mount_points integer,
    fuel_capacity integer,
    required_power integer,
    required_crew integer,
    required_slots integer
);


ALTER TABLE public.ship_frames OWNER TO spacetraders;

--
-- TOC entry 205 (class 1259 OID 16630)
-- Name: ship_nav; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.ship_nav (
    ship_symbol text NOT NULL,
    system_symbol text NOT NULL,
    waypoint_symbol text NOT NULL,
    departure_time timestamp without time zone NOT NULL,
    arrival_time timestamp without time zone NOT NULL,
    origin_waypoint text NOT NULL,
    destination_waypoint text NOT NULL,
    flight_status text NOT NULL,
    flight_mode text NOT NULL
);


ALTER TABLE public.ship_nav OWNER TO spacetraders;

--
-- TOC entry 246 (class 1259 OID 27142)
-- Name: ship_overview; Type: VIEW; Schema: public; Owner: spacetraders
--

CREATE VIEW public.ship_overview AS
 SELECT s.ship_symbol,
    s.ship_role,
    sfl.frame_symbol,
    sn.waypoint_symbol,
    s.cargo_in_use,
    s.cargo_capacity,
    sb.behaviour_id,
    sb.locked_until,
    date_trunc('SECONDS'::text, s.last_updated) AS last_updated
   FROM (((public.ship s
     LEFT JOIN public.ship_behaviours sb ON ((s.ship_symbol = sb.ship_symbol)))
     JOIN public.ship_frame_links sfl ON ((s.ship_symbol = sfl.ship_symbol)))
     JOIN public.ship_nav sn ON ((s.ship_symbol = sn.ship_symbol)))
  ORDER BY s.last_updated DESC;


ALTER TABLE public.ship_overview OWNER TO spacetraders;

--
-- TOC entry 245 (class 1259 OID 27118)
-- Name: shipyard_prices; Type: VIEW; Schema: public; Owner: spacetraders
--

CREATE VIEW public.shipyard_prices AS
 WITH ranked_shipyard AS (
         SELECT shipyard_types.ship_type,
            shipyard_types.ship_cost,
            shipyard_types.shipyard_symbol,
            row_number() OVER (PARTITION BY shipyard_types.ship_type ORDER BY shipyard_types.ship_cost, shipyard_types.shipyard_symbol) AS rank
           FROM public.shipyard_types
        )
 SELECT st.ship_type,
    min(st.ship_cost) AS best_price,
    count(
        CASE
            WHEN (st.ship_cost IS NOT NULL) THEN 1
            ELSE NULL::integer
        END) AS sources,
    count(*) AS locations,
    rs.shipyard_symbol AS cheapest_location
   FROM (public.shipyard_types st
     LEFT JOIN ranked_shipyard rs ON ((st.ship_type = rs.ship_type)))
  WHERE (rs.rank = 1)
  GROUP BY st.ship_type, rs.shipyard_symbol
  ORDER BY st.ship_type;


ALTER TABLE public.shipyard_prices OWNER TO spacetraders;

--
-- TOC entry 215 (class 1259 OID 16800)
-- Name: survey; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.survey (
    signature text NOT NULL,
    waypoint text,
    expiration timestamp without time zone,
    size text
);


ALTER TABLE public.survey OWNER TO spacetraders;

--
-- TOC entry 221 (class 1259 OID 17165)
-- Name: survey_average_values; Type: VIEW; Schema: public; Owner: spacetraders
--

CREATE VIEW public.survey_average_values AS
SELECT
    NULL::text AS signature,
    NULL::text AS waypoint,
    NULL::timestamp without time zone AS expiration,
    NULL::text AS size,
    NULL::numeric AS survey_value;


ALTER TABLE public.survey_average_values OWNER TO spacetraders;

--
-- TOC entry 216 (class 1259 OID 16808)
-- Name: survey_deposit; Type: TABLE; Schema: public; Owner: spacetraders
--

CREATE TABLE public.survey_deposit (
    signature text NOT NULL,
    symbol text NOT NULL,
    count integer
);


ALTER TABLE public.survey_deposit OWNER TO spacetraders;

--
-- TOC entry 222 (class 1259 OID 17170)
-- Name: survey_chance_and_values; Type: VIEW; Schema: public; Owner: spacetraders
--

CREATE VIEW public.survey_chance_and_values AS
 WITH totals AS (
         SELECT sd_1.signature,
            count(*) AS total_deposits
           FROM public.survey_deposit sd_1
          GROUP BY sd_1.signature
        )
 SELECT sd.signature,
    sd.symbol,
    sd.count,
    tot.total_deposits,
    round(((sd.count)::numeric / (tot.total_deposits)::numeric), 2) AS chance,
    sav.survey_value
   FROM (((public.survey_deposit sd
     JOIN public.survey s ON ((s.signature = sd.signature)))
     JOIN totals tot ON ((sd.signature = tot.signature)))
     JOIN public.survey_average_values sav ON ((sd.signature = sav.signature)))
  WHERE (s.expiration >= timezone('utc'::text, now()))
  ORDER BY (round(((sd.count)::numeric / (tot.total_deposits)::numeric), 2)) DESC, sav.survey_value DESC;


ALTER TABLE public.survey_chance_and_values OWNER TO spacetraders;

--
-- TOC entry 224 (class 1259 OID 17561)
-- Name: waypoint_types_not_scanned_by_system; Type: VIEW; Schema: public; Owner: spacetraders
--

CREATE VIEW public.waypoint_types_not_scanned_by_system AS
 SELECT w.type,
    w.system_symbol
   FROM (public.waypoints w
     LEFT JOIN public.waypoint_traits wt ON ((w.symbol = wt.waypoint)))
  GROUP BY w.type, w.system_symbol
 HAVING (count(wt.symbol) = 0);


ALTER TABLE public.waypoint_types_not_scanned_by_system OWNER TO spacetraders;

--
-- TOC entry 223 (class 1259 OID 17532)
-- Name: waypoints_not_scanned; Type: VIEW; Schema: public; Owner: spacetraders
--

CREATE VIEW public.waypoints_not_scanned AS
 SELECT w.symbol,
    w.type,
    w.system_symbol,
    w.x,
    w.y
   FROM public.waypoints w
  WHERE (NOT w.checked);


ALTER TABLE public.waypoints_not_scanned OWNER TO spacetraders;

--
-- TOC entry 231 (class 1259 OID 18274)
-- Name: waypoints_not_scanned_progress; Type: VIEW; Schema: public; Owner: spacetraders
--

CREATE VIEW public.waypoints_not_scanned_progress AS
 WITH waypoint_scan_progress AS (
         SELECT count(wns.*) AS remaining,
            count(*) AS total
           FROM (public.waypoints_not_scanned wns
             RIGHT JOIN public.waypoints w ON ((wns.symbol = w.symbol)))
          WHERE (w.type = ANY (ARRAY['ORBITAL_STATION'::text, 'ASTEROID_FIELD'::text, 'JUMP_GATE'::text]))
        )
 SELECT 'Waypoint scanning progress'::text AS "?column?",
    (waypoint_scan_progress.total - waypoint_scan_progress.remaining) AS scanned,
    waypoint_scan_progress.total,
    round(((((waypoint_scan_progress.total - waypoint_scan_progress.remaining))::numeric / (waypoint_scan_progress.total)::numeric) * (100)::numeric), 2) AS progress
   FROM waypoint_scan_progress;


ALTER TABLE public.waypoints_not_scanned_progress OWNER TO spacetraders;

--
-- TOC entry 3103 (class 2606 OID 16695)
-- Name: agents agents_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.agents
    ADD CONSTRAINT agents_pkey PRIMARY KEY (symbol);


--
-- TOC entry 3117 (class 2606 OID 16903)
-- Name: contract_tradegoods contract_tradegoods_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.contract_tradegoods
    ADD CONSTRAINT contract_tradegoods_pkey PRIMARY KEY (contract_id, trade_symbol);


--
-- TOC entry 3115 (class 2606 OID 16893)
-- Name: contracts contracts_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT contracts_pkey PRIMARY KEY (id);


--
-- TOC entry 3119 (class 2606 OID 17765)
-- Name: jump_gates jump_gates_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.jump_gates
    ADD CONSTRAINT jump_gates_pkey PRIMARY KEY (waypoint_symbol);


--
-- TOC entry 3121 (class 2606 OID 17773)
-- Name: jumpgate_connections jumpgate_connections_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.jumpgate_connections
    ADD CONSTRAINT jumpgate_connections_pkey PRIMARY KEY (source_waypoint, destination_waypoint);


--
-- TOC entry 3105 (class 2606 OID 16703)
-- Name: logging logging_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.logging
    ADD CONSTRAINT logging_pkey PRIMARY KEY (event_timestamp, ship_name);


--
-- TOC entry 3083 (class 2606 OID 16669)
-- Name: market market_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.market
    ADD CONSTRAINT market_pkey PRIMARY KEY (symbol);


--
-- TOC entry 3085 (class 2606 OID 16671)
-- Name: market_tradegood market_tradegood_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.market_tradegood
    ADD CONSTRAINT market_tradegood_pkey PRIMARY KEY (market_waypoint, symbol);


--
-- TOC entry 3109 (class 2606 OID 16719)
-- Name: ship_behaviours ship_behaviours_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.ship_behaviours
    ADD CONSTRAINT ship_behaviours_pkey PRIMARY KEY (ship_symbol);


--
-- TOC entry 3123 (class 2606 OID 18063)
-- Name: ship_cooldowns ship_cooldown_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.ship_cooldowns
    ADD CONSTRAINT ship_cooldown_pkey PRIMARY KEY (ship_symbol, expiration);


--
-- TOC entry 3107 (class 2606 OID 16711)
-- Name: ship_frame_links ship_frame_links_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.ship_frame_links
    ADD CONSTRAINT ship_frame_links_pkey PRIMARY KEY (ship_symbol, frame_symbol);


--
-- TOC entry 3101 (class 2606 OID 16667)
-- Name: ship_frames ship_frames_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.ship_frames
    ADD CONSTRAINT ship_frames_pkey PRIMARY KEY (frame_symbol);


--
-- TOC entry 3091 (class 2606 OID 16673)
-- Name: ship_nav ship_nav_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.ship_nav
    ADD CONSTRAINT ship_nav_pkey PRIMARY KEY (ship_symbol);


--
-- TOC entry 3089 (class 2606 OID 16675)
-- Name: ship ship_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.ship
    ADD CONSTRAINT ship_pkey PRIMARY KEY (ship_symbol);


--
-- TOC entry 3093 (class 2606 OID 16677)
-- Name: shipyard_types shipyard_types_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.shipyard_types
    ADD CONSTRAINT shipyard_types_pkey PRIMARY KEY (shipyard_symbol, ship_type);


--
-- TOC entry 3113 (class 2606 OID 16815)
-- Name: survey_deposit survey_deposit_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.survey_deposit
    ADD CONSTRAINT survey_deposit_pkey PRIMARY KEY (signature, symbol);


--
-- TOC entry 3111 (class 2606 OID 16807)
-- Name: survey survey_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.survey
    ADD CONSTRAINT survey_pkey PRIMARY KEY (signature);


--
-- TOC entry 3095 (class 2606 OID 16679)
-- Name: systems systems_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.systems
    ADD CONSTRAINT systems_pkey PRIMARY KEY (symbol);


--
-- TOC entry 3087 (class 2606 OID 16681)
-- Name: market_tradegood_listing tradegoods_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.market_tradegood_listing
    ADD CONSTRAINT tradegoods_pkey PRIMARY KEY (market_symbol, symbol);


--
-- TOC entry 3127 (class 2606 OID 26908)
-- Name: transactions transaction_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transaction_pkey PRIMARY KEY ("timestamp", ship_symbol);


--
-- TOC entry 3125 (class 2606 OID 18368)
-- Name: waypoint_charts waypoint_charts_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.waypoint_charts
    ADD CONSTRAINT waypoint_charts_pkey PRIMARY KEY (waypoint_symbol);


--
-- TOC entry 3099 (class 2606 OID 16683)
-- Name: waypoints waypoint_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.waypoints
    ADD CONSTRAINT waypoint_pkey PRIMARY KEY (symbol);


--
-- TOC entry 3097 (class 2606 OID 16685)
-- Name: waypoint_traits waypoint_traits_pkey; Type: CONSTRAINT; Schema: public; Owner: spacetraders
--

ALTER TABLE ONLY public.waypoint_traits
    ADD CONSTRAINT waypoint_traits_pkey PRIMARY KEY (waypoint, symbol);


--
-- TOC entry 3262 (class 2618 OID 17168)
-- Name: survey_average_values _RETURN; Type: RULE; Schema: public; Owner: spacetraders
--

CREATE OR REPLACE VIEW public.survey_average_values AS
 SELECT s.signature,
    s.waypoint,
    s.expiration,
    s.size,
    sum((mp.sell_price * (sd.count)::numeric)) AS survey_value
   FROM ((public.survey s
     JOIN public.survey_deposit sd ON ((s.signature = sd.signature)))
     JOIN public.market_prices mp ON ((mp.symbol = sd.symbol)))
  WHERE (s.expiration >= timezone('utc'::text, now()))
  GROUP BY s.signature, s.waypoint, s.expiration
  ORDER BY (sum((mp.sell_price * (sd.count)::numeric))) DESC;


--
-- TOC entry 3128 (class 2620 OID 16686)
-- Name: ship update_a_last_updated; Type: TRIGGER; Schema: public; Owner: spacetraders
--

CREATE TRIGGER update_a_last_updated AFTER UPDATE ON public.ship FOR EACH ROW EXECUTE FUNCTION public.update_last_updated();


--
-- TOC entry 3129 (class 2620 OID 16687)
-- Name: ship update_ship_last_updated; Type: TRIGGER; Schema: public; Owner: spacetraders
--

CREATE TRIGGER update_ship_last_updated AFTER UPDATE ON public.ship FOR EACH ROW EXECUTE FUNCTION public.update_last_updated();


--
-- TOC entry 3288 (class 0 OID 0)
-- Dependencies: 6
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: postgres
--

REVOKE USAGE ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO PUBLIC;
GRANT ALL ON SCHEMA public TO spacetraders;


-- Completed on 2023-08-19 11:41:19

--
-- PostgreSQL database dump complete
--

