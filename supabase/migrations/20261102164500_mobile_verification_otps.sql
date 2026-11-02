-- Migration: 20261102164500_mobile_verification_otps.sql
-- Mobile OTP verification for phone authentication, signup, and login

CREATE TABLE IF NOT EXISTS public.mobile_verification_otps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mobile TEXT NOT NULL,
    otp_hash TEXT NOT NULL,
    purpose TEXT NOT NULL DEFAULT 'login',
    role TEXT NOT NULL DEFAULT 'creator',
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mobile_otp_lookup ON public.mobile_verification_otps (mobile, expires_at);
ALTER TABLE public.mobile_verification_otps ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.mobile_verification_otps FROM anon, authenticated;
GRANT ALL PRIVILEGES ON public.mobile_verification_otps TO postgres, service_role, collivra_app;
