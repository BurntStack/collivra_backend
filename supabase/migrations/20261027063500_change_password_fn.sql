create or replace function public.change_user_password(uid uuid, current_pass text, new_pass text)
returns boolean
language plpgsql
security definer
as $$
declare
  v_hash text;
begin
  select encrypted_password into v_hash
  from auth.users
  where id = uid;

  if v_hash is null or v_hash != crypt(current_pass, v_hash) then
    return false;
  end if;

  update auth.users
  set encrypted_password = crypt(new_pass, gen_salt('bf', 10)),
      updated_at = now()
  where id = uid;

  return true;
end;
$$;

revoke all on function public.change_user_password(uuid, text, text) from public, anon, authenticated;
grant execute on function public.change_user_password(uuid, text, text) to service_role;
