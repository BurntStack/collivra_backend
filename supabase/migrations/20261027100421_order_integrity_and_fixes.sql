-- =============================================================================
-- Migration: 20261027100421_order_integrity_and_fixes.sql
-- =============================================================================

-- 1. Fix handle_new_user trigger function & trigger
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_role text;
  v_status text;
  v_name text;
  v_mobile text;
  v_company_name text;
  v_provider text;
  v_terms_version text;
  v_terms_accepted_at timestamptz;
  v_app_role text;
begin
  v_app_role := new.raw_app_meta_data->>'role';
  v_provider := coalesce(new.raw_app_meta_data->>'provider', 'email');

  -- Trusted app_metadata check: only admin and super_admin are trusted from app_metadata and start as active
  if v_app_role in ('admin', 'super_admin') then
    v_role := v_app_role;
    v_status := 'active';
  else
    -- User metadata or OAuth defaults
    v_role := new.raw_user_meta_data->>'role';
    if v_role is null and (v_provider = 'google' or v_provider = 'apple') then
      v_role := 'brand';
    end if;

    if v_role in ('brand', 'creator') then
      v_status := 'unverified';
    elsif TG_OP = 'INSERT' and v_app_role is null and v_role is null then
      v_role := 'brand';
      v_status := 'unverified';
    else
      raise exception 'A valid role (brand or creator) is required to sign up'
        using errcode = 'P0001';
    end if;
  end if;

  v_name := coalesce(
    new.raw_user_meta_data->>'name',
    new.raw_user_meta_data->>'full_name',
    ''
  );
  v_mobile := new.raw_user_meta_data->>'mobile';
  v_company_name := new.raw_user_meta_data->>'company_name';
  v_terms_version := new.raw_user_meta_data->>'terms_version';
  if v_terms_version is not null then
    v_terms_accepted_at := clock_timestamp();
  else
    v_terms_accepted_at := null;
  end if;

  insert into public.profiles (
    id,
    role,
    name,
    mobile,
    email,
    company_name,
    status,
    terms_version,
    terms_accepted_at
  ) values (
    new.id,
    v_role::public.user_role,
    v_name,
    v_mobile,
    new.email,
    v_company_name,
    v_status::public.account_status,
    v_terms_version,
    v_terms_accepted_at
  )
  on conflict (id) do update set
    role = excluded.role,
    status = case when excluded.role in ('admin', 'super_admin') then 'active'::public.account_status else public.profiles.status end,
    name = coalesce(nullif(excluded.name, ''), public.profiles.name),
    mobile = coalesce(excluded.mobile, public.profiles.mobile),
    company_name = coalesce(excluded.company_name, public.profiles.company_name);

  if v_role = 'brand' then
    insert into public.brand_profiles (user_id, company_name)
    values (new.id, v_company_name)
    on conflict (user_id) do update set company_name = coalesce(excluded.company_name, public.brand_profiles.company_name);
  end if;

  return new;
end;
$$;

revoke all on function public.handle_new_user() from public, anon, authenticated;
grant execute on function public.handle_new_user() to service_role;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert or update of raw_app_meta_data on auth.users
  for each row execute function public.handle_new_user();

-- 2. Orders constraints, status extension, funded_at, and revision count
alter table public.orders drop constraint if exists orders_status_check;
alter table public.orders add constraint orders_status_check 
  check (status in ('awaiting_payment', 'in_escrow', 'draft_submitted', 'changes_requested', 'released', 'completed', 'cancelled'));

alter table public.orders add column if not exists revision_count integer not null default 0;
alter table public.orders add column if not exists funded_at timestamptz;

-- 3. Cancel existing unpaid in_escrow test orders
update public.orders set status = 'cancelled' where status = 'in_escrow';

-- 4. Bid ID on orders and unique index (ABOVE select_bid)
alter table public.orders add column if not exists bid_id uuid references public.campaign_bids(id);
create unique index if not exists unique_order_per_bid on public.orders (bid_id) where bid_id is not null;

-- 5. Unique active order per campaign
create unique index if not exists unique_active_order_per_campaign 
  on public.orders (campaign_id) 
  where status != 'cancelled';

-- 6. select_bid atomic function
create or replace function public.select_bid(
  p_campaign_id uuid,
  p_bid_id uuid,
  p_brand_id uuid
)
returns public.orders
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_campaign public.campaigns;
  v_bid public.campaign_bids;
  v_order public.orders;
begin
  -- Lock campaign row for update
  select * into v_campaign
  from public.campaigns
  where id = p_campaign_id and deleted_at is null
  for update;

  if not found then
    raise exception 'Campaign not found' using errcode = 'P0002';
  end if;

  -- Verify ownership
  if v_campaign.brand_id != p_brand_id then
    raise exception 'Unauthorized' using errcode = 'P0003';
  end if;

  -- Verify campaign status: open_for_bids or closed (not awarded, cancelled, or deleted)
  if v_campaign.status not in ('open_for_bids', 'closed') then
    raise exception 'Campaign is not open for selection (status: %)', v_campaign.status using errcode = 'P0004';
  end if;

  -- Verify bid
  select * into v_bid
  from public.campaign_bids
  where id = p_bid_id and campaign_id = p_campaign_id
  for update;

  if not found then
    raise exception 'Bid not found' using errcode = 'P0005';
  end if;

  if v_bid.status not in ('submitted', 'shortlisted') then
    raise exception 'Bid is not eligible for selection (status: %)', v_bid.status using errcode = 'P0006';
  end if;

  -- Create order in awaiting_payment
  insert into public.orders (
    brand_id,
    creator_id,
    campaign_id,
    bid_id,
    deliverable,
    amount,
    status
  ) values (
    p_brand_id,
    v_bid.creator_id,
    p_campaign_id,
    p_bid_id,
    v_campaign.deliverables,
    v_bid.price,
    'awaiting_payment'
  )
  returning * into v_order;

  -- Update campaign status to awarded
  update public.campaigns
  set status = 'awarded', updated_at = clock_timestamp()
  where id = p_campaign_id;

  -- Update winning bid to selected
  update public.campaign_bids
  set status = 'selected'
  where id = p_bid_id;

  -- Update rival bids to rejected (only submitted or shortlisted)
  update public.campaign_bids
  set status = 'rejected'
  where campaign_id = p_campaign_id and id <> p_bid_id and status in ('submitted', 'shortlisted');

  return v_order;
end;
$$;

revoke all on function public.select_bid(uuid, uuid, uuid) from public, anon, authenticated;
grant execute on function public.select_bid(uuid, uuid, uuid) to service_role;

-- 7. Cart database constraints
update public.cart_items set quantity = 20 where quantity > 20;
update public.cart_items set quantity = 1 where quantity < 1;
alter table public.cart_items drop constraint if exists cart_quantity_range;
alter table public.cart_items add constraint cart_quantity_range check (quantity between 1 and 20);

-- 8. Creator status & creator packages active flag
alter table public.creators 
  add column if not exists status text not null default 'active';

alter table public.creator_packages 
  add column if not exists is_active boolean not null default true;

-- 9. Seed data flags
alter table public.creators 
  add column if not exists is_seed boolean not null default false;

alter table public.deliverables 
  add column if not exists is_seed boolean not null default false;

-- Mark seeded creators and deliverables
update public.creators set is_seed = true where id in ('ananya-rao', 'rohan-verma', 'neha-sharma');
update public.deliverables set is_seed = true;
