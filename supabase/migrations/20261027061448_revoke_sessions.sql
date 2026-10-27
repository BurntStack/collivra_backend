create or replace function public.revoke_user_sessions(uid uuid)
returns void
language sql
security definer
as $$
  delete from auth.refresh_tokens where user_id = uid::text;
  delete from auth.sessions where user_id = uid;
$$;

revoke all on function public.revoke_user_sessions(uuid) from public, anon, authenticated;
grant execute on function public.revoke_user_sessions(uuid) to service_role;
