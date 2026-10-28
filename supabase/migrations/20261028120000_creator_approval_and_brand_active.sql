-- Migration: Creator approval flow and immediate active brands
-- Sets new brands to status 'active' on INSERT
-- Sets new creators to status 'unverified' on INSERT
-- Promotes admin/super_admin only from raw_app_meta_data
-- Updates existing brand profiles from 'unverified' to 'active'

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
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
  -- Check if this is an update to raw_app_meta_data on auth.users
  if TG_OP = 'UPDATE' then
    v_app_role := new.raw_app_meta_data->>'role';
    -- ONLY promote to admin or super_admin if specified in raw_app_meta_data.
    -- Role and status are NEVER read from raw_user_meta_data on UPDATE.
    if v_app_role in ('admin', 'super_admin') then
      update public.profiles 
      set role = v_app_role::public.user_role, 
          status = 'active'::public.account_status,
          updated_at = clock_timestamp()
      where id = new.id;
    end if;
    return new;
  end if;

  -- TG_OP = 'INSERT'
  v_app_role := new.raw_app_meta_data->>'role';
  v_provider := coalesce(new.raw_app_meta_data->>'provider', 'email');

  if v_app_role in ('admin', 'super_admin') then
    v_role := v_app_role;
    v_status := 'active';
  else
    v_role := new.raw_user_meta_data->>'role';
    if v_role is null and (v_provider = 'google' or v_provider = 'apple') then
      v_role := 'brand';
    end if;

    if v_role is null or v_role = 'brand' then
      v_role := 'brand';
      v_status := 'active';
    elsif v_role = 'creator' then
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
    name = excluded.name,
    mobile = excluded.mobile,
    company_name = excluded.company_name;

  if v_role = 'brand' then
    insert into public.brand_profiles (user_id, company_name)
    values (new.id, v_company_name)
    on conflict (user_id) do update set company_name = excluded.company_name;
  end if;

  return new;
end;
$function$;

-- Update existing brand profiles from 'unverified' to 'active'
UPDATE public.profiles
SET status = 'active'
WHERE role = 'brand' AND status = 'unverified';
