SELECT 'CREATE DATABASE ducklake OWNER abi'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ducklake')\gexec

\connect ducklake

CREATE SCHEMA IF NOT EXISTS public;

GRANT ALL PRIVILEGES ON DATABASE ducklake TO abi;
GRANT ALL PRIVILEGES ON SCHEMA public TO abi;
