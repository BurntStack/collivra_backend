-- Migration: 20261028123500_email_verification_otps.sql
-- Email OTP verification for two-step signup

ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS email_verified_at timestamptz;

CREATE TABLE IF NOT EXISTS public.email_verification_otps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL,
    otp_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'brand',
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS idx_email_otp_lookup ON public.email_verification_otps (email, expires_at);

ALTER TABLE public.email_verification_otps ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.email_verification_otps FROM anon, authenticated;
GRANT ALL PRIVILEGES ON public.email_verification_otps TO postgres, service_role, collivra_app;
