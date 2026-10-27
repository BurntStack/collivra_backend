-- Add escrow and deliverable columns to orders if not present
alter table public.orders 
  add column if not exists payment_intent text,
  add column if not exists client_secret text,
  add column if not exists change_note text,
  add column if not exists draft_url text,
  add column if not exists released_at timestamptz;

-- Order chat thread / messages
create table if not exists public.order_messages (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders(id) on delete cascade,
  sender_id uuid references public.profiles(id) on delete set null,
  sender_name text,
  sender_role text check (sender_role in ('brand', 'creator', 'system')),
  message text not null,
  attachments jsonb default '[]'::jsonb,
  created_at timestamptz not null default now()
);

-- RLS for order_messages
alter table public.order_messages enable row level security;

grant select, insert, update, delete on public.order_messages to authenticated;

create policy "order participants can view order messages" on public.order_messages
  for select using (
    exists (
      select 1 from public.orders
      where orders.id = order_messages.order_id
        and orders.brand_id = auth.uid()
    )
  );

create policy "order participants can insert order messages" on public.order_messages
  for insert with check (
    exists (
      select 1 from public.orders
      where orders.id = order_messages.order_id
        and orders.brand_id = auth.uid()
    )
  );
