-- Cart items table
create table if not exists public.cart_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  creator_id text not null references public.creators(id) on delete cascade,
  package_id text not null references public.creator_packages(id) on delete cascade,
  quantity int not null default 1 check (quantity > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, creator_id, package_id)
);

create trigger cart_items_updated_at before update on public.cart_items
  for each row execute function public.set_updated_at();

-- Custom offers table
create table if not exists public.custom_offers (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references public.profiles(id) on delete cascade,
  creator_id text not null references public.creators(id) on delete cascade,
  deliverable text not null,
  budget int not null check (budget > 0),
  message text,
  deadline text,
  status text not null default 'pending' check (status in ('pending', 'accepted', 'declined', 'expired')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger custom_offers_updated_at before update on public.custom_offers
  for each row execute function public.set_updated_at();

-- Access rules & RLS
alter table public.cart_items enable row level security;
alter table public.custom_offers enable row level security;

grant select, insert, update, delete on public.cart_items to authenticated;
grant select, insert, update, delete on public.custom_offers to authenticated;

-- Cart items policies
create policy "own cart items select" on public.cart_items
  for select using (user_id = auth.uid());

create policy "own cart items insert" on public.cart_items
  for insert with check (user_id = auth.uid());

create policy "own cart items update" on public.cart_items
  for update using (user_id = auth.uid());

create policy "own cart items delete" on public.cart_items
  for delete using (user_id = auth.uid());

-- Custom offers policies
create policy "brand read own offers" on public.custom_offers
  for select using (brand_id = auth.uid());

create policy "brand create offers" on public.custom_offers
  for insert with check (brand_id = auth.uid());

create policy "brand update own offers" on public.custom_offers
  for update using (brand_id = auth.uid());

create policy "brand delete own offers" on public.custom_offers
  for delete using (brand_id = auth.uid());
