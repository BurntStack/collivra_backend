alter table public.profiles add column mobile_verified_at timestamptz;

create table public.otp_send_log (
  id bigint generated always as identity primary key,
  mobile text not null,
  purpose text not null,
  created_at timestamptz not null default now()
);
create index otp_send_log_mobile_time on public.otp_send_log (mobile, created_at desc);

alter table public.otp_send_log enable row level security;
revoke all on public.otp_send_log from anon, authenticated;
