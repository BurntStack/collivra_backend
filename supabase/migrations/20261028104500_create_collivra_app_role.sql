-- Create collivra_app role for application database access (least privilege, non-superuser).
-- SECURITY NOTE: Never commit passwords to git. The role password must be set manually
-- in the Supabase SQL Editor:
--     ALTER ROLE collivra_app WITH PASSWORD '<generated_secret>';
-- And configured only in Render's DATABASE_URL environment variable:
--     DATABASE_URL=postgresql://collivra_app:<generated_secret>@<host>:6543/postgres?sslmode=require
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'collivra_app') THEN
        -- Password intentionally omitted from repository files.
        CREATE ROLE collivra_app WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;
END
$$;

GRANT CONNECT ON DATABASE postgres TO collivra_app;
GRANT USAGE ON SCHEMA public TO collivra_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO collivra_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO collivra_app;
GRANT ALL PRIVILEGES ON ALL ROUTINES IN SCHEMA public TO collivra_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO collivra_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO collivra_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON ROUTINES TO collivra_app;
