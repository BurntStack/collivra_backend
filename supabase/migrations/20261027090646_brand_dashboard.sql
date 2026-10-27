-- Brand onboarding todo items
create table if not exists public.brand_todos (
  user_id uuid not null references public.profiles(id) on delete cascade,
  todo_id text not null,
  label text not null,
  done boolean not null default false,
  updated_at timestamptz not null default now(),
  primary key (user_id, todo_id)
);

-- Shortlists / Lists
create table if not exists public.shortlists (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references public.profiles(id) on delete cascade,
  name text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger shortlists_updated_at before update on public.shortlists
  for each row execute function public.set_updated_at();

create table if not exists public.shortlist_creators (
  id uuid primary key default gen_random_uuid(),
  list_id uuid not null references public.shortlists(id) on delete cascade,
  creator_id text not null references public.creators(id) on delete cascade,
  created_at timestamptz not null default now(),
  unique(list_id, creator_id)
);

-- Deliverables (Content library)
create table if not exists public.deliverables (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references public.profiles(id) on delete cascade,
  creator_id text not null references public.creators(id) on delete cascade,
  campaign_id uuid references public.campaigns(id) on delete set null,
  order_id uuid references public.orders(id) on delete set null,
  content text not null,
  type text not null,
  platform text not null,
  status text not null check (status in ('Approved', 'Needs review', 'Live', 'Revision asked')),
  preview_url text not null,
  download_url text not null,
  delivered_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

-- RLS
alter table public.brand_todos enable row level security;
alter table public.shortlists enable row level security;
alter table public.shortlist_creators enable row level security;
alter table public.deliverables enable row level security;

grant select, insert, update, delete on public.brand_todos to authenticated;
grant select, insert, update, delete on public.shortlists to authenticated;
grant select, insert, update, delete on public.shortlist_creators to authenticated;
grant select, insert, update, delete on public.deliverables to authenticated;

create policy "brands manage own todos" on public.brand_todos
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy "brands manage own shortlists" on public.shortlists
  for all using (brand_id = auth.uid()) with check (brand_id = auth.uid());

create policy "brands manage own shortlist creators" on public.shortlist_creators
  for all using (
    exists (select 1 from public.shortlists where shortlists.id = shortlist_creators.list_id and shortlists.brand_id = auth.uid())
  ) with check (
    exists (select 1 from public.shortlists where shortlists.id = shortlist_creators.list_id and shortlists.brand_id = auth.uid())
  );

create policy "brands manage own deliverables" on public.deliverables
  for all using (brand_id = auth.uid()) with check (brand_id = auth.uid());
