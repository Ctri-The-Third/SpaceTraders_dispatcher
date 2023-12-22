FROM postgres:latest

ENV POSTGRES_USER=spacetraders
run mkdir -p /docker-entrypoint-initdb.d 

copy ./spacetraders_sdk/PostgresSchema.SQL /docker-entrypoint-initdb.d/PostgresSchema.SQL

