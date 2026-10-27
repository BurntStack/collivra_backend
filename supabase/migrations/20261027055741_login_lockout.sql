alter table public.profiles
  add column failed_logins int not null default 0,
  add column locked_until timestamptz;
