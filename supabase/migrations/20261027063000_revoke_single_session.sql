create or replace function public.revoke_session_by_refresh_token(p_refresh_token text)
returns void
language plpgsql
security definer
as $$
declare
  v_session_id uuid;
begin
  select session_id into v_session_id
  from auth.refresh_tokens
  where token = p_refresh_token
  limit 1;

  if v_session_id is not null then
    delete from auth.refresh_tokens where session_id = v_session_id;
    delete from auth.sessions where id = v_session_id;
  else
    delete from auth.refresh_tokens where token = p_refresh_token;
  end if;
end;
$$;

revoke all on function public.revoke_session_by_refresh_token(text) from public, anon, authenticated;
grant execute on function public.revoke_session_by_refresh_token(text) to service_role;
