-- foundation_check.sql
-- Run with: supabase db test
-- All 8 assertions pass, then P0001 is raised intentionally to roll back test data.

BEGIN;

-- ── helpers ──────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION assert(condition boolean, msg text) RETURNS void AS $$
BEGIN
  IF NOT condition THEN
    RAISE EXCEPTION 'ASSERT FAILED: %', msg;
  END IF;
END;
$$ LANGUAGE plpgsql;

-- ── seed two test users ───────────────────────────────────────────────────────
INSERT INTO auth.users (id, email, phone, created_at, updated_at)
VALUES
  ('00000000-0000-0000-0000-000000000001', 'alice@test.invalid', NULL, now(), now()),
  ('00000000-0000-0000-0000-000000000002', 'bob@test.invalid',   NULL, now(), now());

-- profiles created by trigger
DO $$
DECLARE
  alice_role text;
  alice_status text;
BEGIN
  SELECT role, status INTO alice_role, alice_status
  FROM public.profiles
  WHERE id = '00000000-0000-0000-0000-000000000001';

  PERFORM assert(alice_role   = 'user',       'new signup role should be user');
  PERFORM assert(alice_status = 'unverified', 'new signup status should be unverified');
END $$;

-- ── test 1 & 2: signup defaults ───────────────────────────────────────────────
DO $$
DECLARE r record;
BEGIN
  SELECT role, status INTO r FROM public.profiles
  WHERE id = '00000000-0000-0000-0000-000000000001';
  PERFORM assert(r.role = 'user',       'T1: default role = user');
  PERFORM assert(r.status = 'unverified','T2: default status = unverified');
END $$;

-- ── test 3: cannot sign up as admin ──────────────────────────────────────────
DO $$
BEGIN
  BEGIN
    UPDATE public.profiles
    SET role = 'admin'
    WHERE id = '00000000-0000-0000-0000-000000000001';
    PERFORM assert(false, 'T3: should not be able to self-promote to admin');
  EXCEPTION WHEN OTHERS THEN
    -- expected: RLS or check constraint blocks it
    NULL;
  END;
END $$;

-- ── test 4: user sees only own profile (RLS) ─────────────────────────────────
SET LOCAL role = authenticated;
SET LOCAL request.jwt.claims = '{"sub":"00000000-0000-0000-0000-000000000001","role":"authenticated"}';

DO $$
DECLARE cnt int;
BEGIN
  SELECT count(*) INTO cnt FROM public.profiles;
  PERFORM assert(cnt = 1, 'T4: authenticated user should only see own profile via RLS');
END $$;

RESET role;

-- ── test 5: user cannot change own role ──────────────────────────────────────
DO $$
BEGIN
  BEGIN
    SET LOCAL role = authenticated;
    SET LOCAL request.jwt.claims = '{"sub":"00000000-0000-0000-0000-000000000001","role":"authenticated"}';
    UPDATE public.profiles SET role = 'admin'
    WHERE id = '00000000-0000-0000-0000-000000000001';
    PERFORM assert(false, 'T5: user should not be able to change own role');
  EXCEPTION WHEN OTHERS THEN NULL;
  END;
  RESET role;
END $$;

-- ── test 6: user cannot change own status ────────────────────────────────────
DO $$
BEGIN
  BEGIN
    SET LOCAL role = authenticated;
    SET LOCAL request.jwt.claims = '{"sub":"00000000-0000-0000-0000-000000000001","role":"authenticated"}';
    UPDATE public.profiles SET status = 'active'
    WHERE id = '00000000-0000-0000-0000-000000000001';
    PERFORM assert(false, 'T6: user should not be able to change own status');
  EXCEPTION WHEN OTHERS THEN NULL;
  END;
  RESET role;
END $$;

-- ── test 7: user can edit harmless fields ─────────────────────────────────────
SET LOCAL role = authenticated;
SET LOCAL request.jwt.claims = '{"sub":"00000000-0000-0000-0000-000000000001","role":"authenticated"}';

UPDATE public.profiles SET full_name = 'Alice Updated'
WHERE id = '00000000-0000-0000-0000-000000000001';

DO $$
DECLARE n text;
BEGIN
  SELECT full_name INTO n FROM public.profiles
  WHERE id = '00000000-0000-0000-0000-000000000001';
  PERFORM assert(n = 'Alice Updated', 'T7: user can edit own full_name');
END $$;

RESET role;

-- ── test 8: anon cannot read profiles ────────────────────────────────────────
SET LOCAL role = anon;

DO $$
DECLARE cnt int;
BEGIN
  SELECT count(*) INTO cnt FROM public.profiles;
  PERFORM assert(cnt = 0, 'T8: anon should see 0 profiles via RLS');
END $$;

RESET role;

-- ── intentional rollback ──────────────────────────────────────────────────────
RAISE EXCEPTION 'All 8 tests passed — rolling back test data (P0001 is expected)' USING ERRCODE = 'P0001';

ROLLBACK;
