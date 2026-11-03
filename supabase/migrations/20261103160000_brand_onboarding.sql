-- Brand Onboarding fields migration
ALTER TABLE public.profiles 
ADD COLUMN IF NOT EXISTS is_profile_completed BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE public.brand_profiles
ADD COLUMN IF NOT EXISTS first_name TEXT,
ADD COLUMN IF NOT EXISTS last_name TEXT,
ADD COLUMN IF NOT EXISTS brand_name TEXT,
ADD COLUMN IF NOT EXISTS brand_logo TEXT,
ADD COLUMN IF NOT EXISTS brand_website TEXT,
ADD COLUMN IF NOT EXISTS country TEXT NOT NULL DEFAULT 'India',
ADD COLUMN IF NOT EXISTS region_state TEXT,
ADD COLUMN IF NOT EXISTS city TEXT,
ADD COLUMN IF NOT EXISTS mobile TEXT,
ADD COLUMN IF NOT EXISTS business_category TEXT,
ADD COLUMN IF NOT EXISTS geographical_scope TEXT,
ADD COLUMN IF NOT EXISTS terms_accepted BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

GRANT ALL PRIVILEGES ON public.brand_profiles TO postgres, service_role, collivra_app;
GRANT ALL PRIVILEGES ON public.profiles TO postgres, service_role, collivra_app;
