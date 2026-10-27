-- Enums
create type public.user_role as enum ('brand', 'creator', 'admin', 'super_admin');
create type public.account_status as enum
  ('unverified', 'pending', 'needs_info', 'active', 'suspended', 'banned');

-- Profiles
create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  role public.user_role not null,
  status public.account_status not null default 'unverified',
  name text,
  mobile text,
  email text,
  language text not null default 'en',
  terms_version text,
  terms_accepted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint mobile_format check (mobile is null or mobile ~ '^\+91[6-9][0-9]{9}$')
);

-- Mobile is unique per role (API spec, page 12)
create unique index profiles_mobile_role_key
  on public.profiles (mobile, role) where mobile is not null;

alter table public.profiles enable row level security;

create function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger profiles_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

-- Signup trigger.
-- raw_app_meta_data can only be set server-side, so it is trusted (staff accounts).
-- raw_user_meta_data comes from the client, so it may only choose brand or creator.
create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  trusted_role text := new.raw_app_meta_data ->> 'role';
  client_role text := new.raw_user_meta_data ->> 'role';
  final_role public.user_role;
begin
  if trusted_role in ('admin', 'super_admin') then
    final_role := trusted_role::public.user_role;
  elsif client_role in ('brand', 'creator') then
    final_role := client_role::public.user_role;
  else
    raise exception 'role must be brand or creator';
  end if;

  insert into public.profiles (id, role, status, name, mobile, email, terms_version, terms_accepted_at)
  values (
    new.id,
    final_role,
    case when final_role in ('admin', 'super_admin')
         then 'active'::public.account_status
         else 'unverified'::public.account_status end,
    new.raw_user_meta_data ->> 'name',
    coalesce(new.raw_user_meta_data ->> 'mobile', new.phone),
    new.email,
    new.raw_user_meta_data ->> 'terms_version',
    case when new.raw_user_meta_data ->> 'terms_version' is not null then now() end
  );
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- RLS helper functions
create function public.app_role()
returns public.user_role
language sql stable security definer
set search_path = ''
as $$ select role from public.profiles where id = auth.uid() $$;

create function public.is_admin()
returns boolean
language sql stable security definer
set search_path = ''
as $$
  select coalesce(
    (select role in ('admin', 'super_admin') from public.profiles where id = auth.uid()),
    false)
$$;

create function public.is_super_admin()
returns boolean
language sql stable security definer
set search_path = ''
as $$
  select coalesce(
    (select role = 'super_admin' from public.profiles where id = auth.uid()),
    false)
$$;

create function public.is_active()
returns boolean
language sql stable security definer
set search_path = ''
as $$
  select coalesce(
    (select status = 'active' from public.profiles where id = auth.uid()),
    false)
$$;

-- Profiles policies
create policy "read own profile" on public.profiles
  for select using (id = auth.uid());

create policy "admins read all profiles" on public.profiles
  for select using (public.is_admin());

create policy "update own profile" on public.profiles
  for update using (id = auth.uid())
  with check (id = auth.uid());

-- Clients can only edit a few harmless columns.
-- Role, status and mobile change only through trusted server code.
revoke all on public.profiles from anon;
revoke insert, delete, update on public.profiles from authenticated;
grant update (name, email, language) on public.profiles to authenticated;

-- Settings: business rules stored as data, not code
create table public.settings (
  key text primary key,
  value jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.settings enable row level security;

create policy "admins read settings" on public.settings
  for select using (public.is_admin());

revoke all on public.settings from anon;
revoke insert, update, delete on public.settings from authenticated;

-- Values are placeholders from the API spec until the founders confirm them
insert into public.settings (key, value) values
  ('fee_percent', '10'),
  ('tds_percent', '1'),
  ('split_first', '70'),
  ('split_last', '30'),
  ('review_days', '7'),
  ('agreement_hours', '48'),
  ('unpaid_selection_hours', '24'),
  ('auto_approve_draft_hours', '48'),
  ('max_revisions', '2');

-- Audit log: insert-only, written by triggers and server functions
create table public.audit_log (
  id bigint generated always as identity primary key,
  actor_id uuid,
  action text not null,
  entity text not null,
  entity_id text,
  details jsonb,
  created_at timestamptz not null default now()
);
alter table public.audit_log enable row level security;

create policy "admins read audit log" on public.audit_log
  for select using (public.is_admin());

revoke all on public.audit_log from anon;
revoke insert, update, delete on public.audit_log from authenticated;