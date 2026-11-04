-- Creator Onboarding and Verification Queue Migration
ALTER TABLE public.profiles
ADD COLUMN IF NOT EXISTS approval_status TEXT NOT NULL DEFAULT 'pending';

ALTER TABLE public.creator_profiles
ADD COLUMN IF NOT EXISTS first_name TEXT,
ADD COLUMN IF NOT EXISTS last_name TEXT,
ADD COLUMN IF NOT EXISTS dob DATE,
ADD COLUMN IF NOT EXISTS gender TEXT,
ADD COLUMN IF NOT EXISTS region_state TEXT,
ADD COLUMN IF NOT EXISTS country TEXT NOT NULL DEFAULT 'India',
ADD COLUMN IF NOT EXISTS instagram_handle TEXT,
ADD COLUMN IF NOT EXISTS youtube_handle TEXT,
ADD COLUMN IF NOT EXISTS tiktok_handle TEXT,
ADD COLUMN IF NOT EXISTS social_links JSONB NOT NULL DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS pan_number TEXT,
ADD COLUMN IF NOT EXISTS kyc_status TEXT NOT NULL DEFAULT 'pending',
ADD COLUMN IF NOT EXISTS approval_status TEXT NOT NULL DEFAULT 'pending';

GRANT ALL PRIVILEGES ON public.creator_profiles TO postgres, service_role, collivra_app;
GRANT ALL PRIVILEGES ON public.profiles TO postgres, service_role, collivra_app;

