-- 1. Campaigns: Add deleted_at for soft deletes and expand allowed statuses
alter table public.campaigns
  add column if not exists deleted_at timestamptz;

alter table public.campaigns
  drop constraint if exists campaigns_status_check;

alter table public.campaigns
  add constraint campaigns_status_check
  check (status in ('draft', 'open_for_bids', 'closed', 'awarded', 'cancelled'));

-- 2. Brand profiles table with nullable company_name
create table if not exists public.brand_profiles (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  company_name text,
  created_at timestamptz not null default now()
);

alter table public.brand_profiles alter column company_name drop not null;
alter table public.brand_profiles enable row level security;
grant select, insert, update, delete on public.brand_profiles to authenticated;

create policy "brands manage own brand_profile" on public.brand_profiles
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- Backfill brand_profiles from profiles where role = 'brand'
insert into public.brand_profiles (user_id, company_name)
select id, company_name from public.profiles where role = 'brand'
on conflict (user_id) do nothing;

-- 3. Update handle_new_user to handle OAuth google/apple and full_name fallback
create or replace function public.handle_new_user()
 returns trigger
 language plpgsql
 security definer
 set search_path to ''
as $function$
declare
  trusted_role text := new.raw_app_meta_data ->> 'role';
  client_role text := new.raw_user_meta_data ->> 'role';
  provider text := new.raw_app_meta_data ->> 'provider';
  final_role public.user_role;
  user_name text := coalesce(new.raw_user_meta_data ->> 'name', new.raw_user_meta_data ->> 'full_name');
begin
  if trusted_role in ('admin', 'super_admin') then
    final_role := trusted_role::public.user_role;
  elsif client_role in ('brand', 'creator') then
    final_role := client_role::public.user_role;
  elsif provider in ('google', 'apple') then
    final_role := 'brand'::public.user_role;
  else
    -- Default to brand if signing up via brand portal with email/company
    final_role := 'brand'::public.user_role;
  end if;

  insert into public.profiles (
    id, role, status, name, mobile, email, company_name, terms_version, terms_accepted_at
  )
  values (
    new.id,
    final_role,
    case when final_role in ('admin', 'super_admin')
         then 'active'::public.account_status
         else 'active'::public.account_status end,
    user_name,
    coalesce(new.raw_user_meta_data ->> 'mobile', new.phone),
    new.email,
    new.raw_user_meta_data ->> 'company_name',
    new.raw_user_meta_data ->> 'terms_version',
    case when new.raw_user_meta_data ->> 'terms_version' is not null then now() end
  );

  if final_role = 'brand' then
    insert into public.brand_profiles (user_id, company_name)
    values (new.id, new.raw_user_meta_data ->> 'company_name')
    on conflict (user_id) do update set company_name = excluded.company_name;
  end if;

  return new;
end;
$function$;

-- 4. B4: Revoke anon access from all public tables, routines, and sequences
revoke all on all tables in schema public from anon;
revoke all on all sequences in schema public from anon;
revoke all on all routines in schema public from anon;

alter default privileges in schema public revoke all on tables from anon;
alter default privileges in schema public revoke all on routines from anon;
alter default privileges in schema public revoke all on sequences from anon;
