-- Campaigns table ("Post a Job")
create table if not exists public.campaigns (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references public.profiles(id) on delete cascade,
  title text not null,
  platform text not null,
  deliverables text not null,
  budget_min int not null check (budget_min >= 0),
  budget_max int not null check (budget_max >= budget_min),
  apply_by text not null,
  brief text,
  status text not null default 'open_for_bids' check (status in ('open_for_bids', 'closed', 'awarded')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger campaigns_updated_at before update on public.campaigns
  for each row execute function public.set_updated_at();

-- Campaign bids table
create table if not exists public.campaign_bids (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns(id) on delete cascade,
  creator_id text not null references public.creators(id) on delete cascade,
  price int not null check (price > 0),
  note text,
  status text not null default 'submitted' check (status in ('submitted', 'selected', 'rejected')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger campaign_bids_updated_at before update on public.campaign_bids
  for each row execute function public.set_updated_at();

-- Orders table ("Money moves only when you approve")
create table if not exists public.orders (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references public.profiles(id) on delete cascade,
  creator_id text not null references public.creators(id) on delete cascade,
  campaign_id uuid references public.campaigns(id) on delete set null,
  bid_id uuid references public.campaign_bids(id) on delete set null,
  package_id text references public.creator_packages(id) on delete set null,
  deliverable text not null,
  amount int not null check (amount > 0),
  status text not null default 'in_escrow' check (status in ('in_escrow', 'draft_submitted', 'changes_requested', 'released', 'completed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger orders_updated_at before update on public.orders
  for each row execute function public.set_updated_at();

-- Access rules & RLS
alter table public.campaigns enable row level security;
alter table public.campaign_bids enable row level security;
alter table public.orders enable row level security;

grant select, insert, update, delete on public.campaigns to authenticated;
grant select, insert, update, delete on public.campaign_bids to authenticated;
grant select, insert, update, delete on public.orders to authenticated;

-- Public can view open campaigns (for marketplace search)
create policy "anyone can view campaigns" on public.campaigns
  for select using (true);

create policy "brand manage own campaigns" on public.campaigns
  for all using (brand_id = auth.uid()) with check (brand_id = auth.uid());

-- Bids policies
create policy "brand view bids for own campaigns" on public.campaign_bids
  for select using (
    exists (select 1 from public.campaigns where campaigns.id = campaign_bids.campaign_id and campaigns.brand_id = auth.uid())
  );

create policy "creator manage own bids" on public.campaign_bids
  for all using (true) with check (true);

-- Orders policies
create policy "brand manage own orders" on public.orders
  for all using (brand_id = auth.uid()) with check (brand_id = auth.uid());
