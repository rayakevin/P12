#!/bin/sh
set -eu

# Le compte du DAG peut créer et alimenter les tables métier, sans droits
# d'administration sur le serveur PostgreSQL.
psql --set ON_ERROR_STOP=1 \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --set database_name="$POSTGRES_DB" \
    --set loader_user="$WAREHOUSE_USER" \
    --set loader_password="$WAREHOUSE_PASSWORD" <<'SQL'
CREATE ROLE :"loader_user"
    LOGIN
    PASSWORD :'loader_password'
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION;

GRANT CONNECT ON DATABASE :"database_name" TO :"loader_user";
GRANT USAGE, CREATE ON SCHEMA public TO :"loader_user";
SQL
