from ..models import Market, MarketTradeGoodListing, Waypoint
import psycopg2
import logging
from datetime import datetime
from ..utils import waypoint_slicer

# from psycopg2 import connection


def _upsert_market(connection, market: Market):
    try:
        system_symbol = waypoint_slicer(market.symbol)
        cursor = connection.cursor()
        sql = """INSERT INTO public.market(
	symbol, system_symbol)
	VALUES (%s, %s) 
    ON CONFLICT (symbol) DO NOTHING;"""

        cursor.execute(sql, (market.symbol, system_symbol))
    except Exception as err:
        logging.error(err)

    sql = """INSERT INTO public.market_tradegood(
        market_waypoint, symbol, buy_or_sell, name, description)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (market_waypoint, symbol) DO NOTHING"""

    for trade_good in market.exports:
        try:
            cursor.execute(
                sql,
                (
                    market.symbol,
                    trade_good.symbol,
                    "sell",
                    trade_good.name,
                    trade_good.description,
                ),
            )
        except Exception as err:
            logging.error(err)
    for trade_good in market.imports:
        try:
            cursor.execute(
                sql,
                (
                    market.symbol,
                    trade_good.symbol,
                    "buy",
                    trade_good.name,
                    trade_good.description,
                ),
            )
        except Exception as err:
            logging.error(err)

    # if market.exchange is not None and len(market.exchange) > 0:

    #    for trade_good in market.exchange:
    #        # cursor.execute(sql, (market.symbol, trade_good.symbol, trade_good.trade_volume
    #        pass

    if market.listings:
        sql = """INSERT INTO public.market_tradegood_listing 
            ( market_symbol, symbol, supply, purchase_price, sell_price, last_updated )
            VALUES ( %s, %s, %s, %s, %s, %s )
            ON CONFLICT (market_symbol, symbol) DO UPDATE
                    SET supply = %s,  purchase_price = %s, sell_price = %s, last_updated = %s"""
        for listing in market.listings:
            listing: MarketTradeGoodListing
            try:
                cursor.execute(
                    sql,
                    (
                        market.symbol,
                        listing.symbol,
                        listing.supply,
                        listing.purchase,
                        listing.sell_price,
                        datetime.now(),
                        listing.supply,
                        listing.purchase,
                        listing.sell_price,
                        datetime.now(),
                    ),
                )
            except Exception as err:
                logging.error(err)
