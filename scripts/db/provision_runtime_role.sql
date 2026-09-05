-- Idempotently provisions `app_runtime`, the non-superuser role the running
-- application connects as to serve requests (never used to run migrations —
-- the owner role in DATABASE_URL keeps doing that unchanged). Without this,
-- FORCE ROW LEVEL SECURITY is a silent no-op: the owner role bypasses RLS as
-- the table owner, and a superuser bypasses it regardless of FORCE.
--
-- Run against the owner-role connection in every environment (local dev,
-- CI, staging, production), after migrations have been applied at least
-- once (so the blanket GRANT below already covers every table that exists).
-- Safe to re-run: every statement is naturally idempotent or guarded below.
--
-- The password is an obvious dev/test-only placeholder, the same discipline
-- already used for Settings.jwt_secret_key / Settings.mfa_secret_encryption_key:
-- every real deployment MUST override it (ALTER ROLE app_runtime WITH
-- PASSWORD '<deploy-secret>') via the deploy pipeline — never a real
-- credential committed here.

DO $$
BEGIN
    CREATE ROLE app_runtime WITH LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD 'CHANGE_ME_IN_PRODUCTION';
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

-- current_database() rather than a hard-coded name, so this script runs
-- unchanged against the real "customer_portal" database and against
-- whatever ephemeral database name tests/conftest.py's testcontainers
-- instance happens to use.
DO $$
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO app_runtime', current_database());
END
$$;

GRANT USAGE ON SCHEMA public TO app_runtime;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_runtime;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_runtime;

-- No FOR ROLE clause: defaults to "objects created by the role executing
-- this statement", i.e. the owner role that also runs every migration —
-- exactly the role whose future CREATE TABLE calls need covering, without
-- hard-coding that role's name (it differs between environments).
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_runtime;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app_runtime;
