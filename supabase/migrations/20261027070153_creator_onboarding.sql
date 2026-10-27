create type public.social_platform as enum ('instagram', 'youtube');
-- 'stub' marks fake data from development mode, so it can never pass as verified
create type public.stats_source as enum ('verified_api', 'self_reported', 'stub');
create type public.verification_type as enum ('brand', 'creator');
create type public.verification_status as enum ('pending', 'needs_info', 'rejected', 'approved');

-- Public-facing creator info
create table public.creator_profiles (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  category text,
  languages text[] not null default '{}',
  city text,
  topics text[] not null default '{}',
  headline text,
  bio text,
  visibility jsonb not null default '{"followers":true,"audience":true,"rates":true}',
  slug text unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint topics_max check (cardinality(topics) <= 10),
  constraint languages_max check (cardinality(languages) <= 10)
);
create trigger creator_profiles_updated_at before update on public.creator_profiles
  for each row execute function public.set_updated_at();

-- Connected Instagram / YouTube accounts
create table public.social_accounts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  platform public.social_platform not null,
  handle text not null,
  external_id text,
  followers int,
  avg_views int,
  engagement numeric(5,2),
  audience jsonb,
  stats_source public.stats_source not null default 'self_reported',
  stats_synced_at timestamptz,
  token_ciphertext text,  -- encrypted OAuth tokens; never returned by any API
  connected_at timestamptz not null default now(),
  unique (user_id, platform)
);
-- The same real account cannot be claimed by two users
create unique index social_accounts_external_key
  on public.social_accounts (platform, external_id) where external_id is not null;

-- KYC and bank details: server-only, encrypted fields
create table public.creator_kyc (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  pan_ciphertext text,
  pan_last4 text,
  name_on_pan text,
  pan_valid boolean,
  pan_name_match boolean,
  id_doc_type text check (id_doc_type in ('aadhaar', 'passport', 'voter_id', 'driving_licence')),
  id_file_key text,
  id_status text not null default 'none' check (id_status in ('none', 'checking', 'verified', 'failed')),
  bank_account_ciphertext text,
  bank_account_last4 text,
  bank_ifsc text,
  bank_holder_name text,
  upi_id text,
  bank_verified boolean,
  bank_name_match boolean,
  provider text not null default 'stub',  -- 'stub' = NOT independently verified
  updated_at timestamptz not null default now()
);
create trigger creator_kyc_updated_at before update on public.creator_kyc
  for each row execute function public.set_updated_at();

-- Review requests for the admin verification queue (brands use it too, later)
create table public.verification_requests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  type public.verification_type not null,
  status public.verification_status not null default 'pending',
  reasons text[] not null default '{}',
  message text,
  reviewer_id uuid references public.profiles(id),
  submitted_at timestamptz not null default now(),
  reviewed_at timestamptz
);
-- At most one open request per user
create unique index verification_one_open_per_user
  on public.verification_requests (user_id) where status in ('pending', 'needs_info');

-- Files uploaded through presigned URLs
create table public.uploads (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.profiles(id) on delete cascade,
  purpose text not null check (purpose in
    ('kyc-id', 'brand-doc', 'logo', 'job-ref', 'draft', 'evidence', 'chat', 'proof')),
  bucket text not null,
  file_key text not null unique,
  content_type text not null,
  size_bytes bigint not null,
  status text not null default 'pending' check (status in ('pending', 'uploaded', 'attached')),
  created_at timestamptz not null default now()
);
create index uploads_cleanup on public.uploads (status, created_at);

-- Private bucket for ID documents (10 MB, images and PDF only)
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('kyc-docs', 'kyc-docs', false, 10485760,
        array['image/jpeg', 'image/png', 'application/pdf'])
on conflict (id) do nothing;

-- Access rules: RLS on everything
alter table public.creator_profiles enable row level security;
alter table public.social_accounts enable row level security;
alter table public.creator_kyc enable row level security;
alter table public.verification_requests enable row level security;
alter table public.uploads enable row level security;

revoke all on public.creator_profiles, public.social_accounts, public.creator_kyc,
  public.verification_requests, public.uploads from anon, authenticated;

-- Clients may read their own rows. All writes go through the API (service role).
grant select on public.creator_profiles, public.verification_requests to authenticated;
grant select (id, user_id, platform, handle, followers, avg_views, engagement, audience,
              stats_source, stats_synced_at, connected_at)
  on public.social_accounts to authenticated;

create policy "own creator profile" on public.creator_profiles
  for select using (user_id = auth.uid());
create policy "admins read creator profiles" on public.creator_profiles
  for select using (public.is_admin());
create policy "own social accounts" on public.social_accounts
  for select using (user_id = auth.uid());
create policy "admins read social accounts" on public.social_accounts
  for select using (public.is_admin());
create policy "own verification requests" on public.verification_requests
  for select using (user_id = auth.uid());
create policy "admins read verification requests" on public.verification_requests
  for select using (public.is_admin());
-- creator_kyc and uploads: no policies on purpose, so only the server can touch them
