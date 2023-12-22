FROM postgres:latest

ENV POSTGRES_USER=spacetraders
run mkdir -p /docker-entrypoint-initdb.d 

copy ./PostgresDBsetup.sql /docker-entrypoint-initdb.d/PostgresDBsetup.sql

