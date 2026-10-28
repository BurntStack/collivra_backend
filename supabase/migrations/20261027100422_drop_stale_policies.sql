-- =============================================================================
-- Migration: 20261027100422_drop_stale_policies.sql
-- Drop every RLS policy in public schema (RLS stays enabled, 0 policies)
-- =============================================================================

do $$
declare r record;
begin
  for r in select schemaname, tablename, policyname from pg_policies where schemaname = 'public' loop
    execute format('drop policy %I on %I.%I', r.policyname, r.schemaname, r.tablename);
  end loop;
end $$;
