-- Enforce single admin email constraint at database level
-- Only socials@burntstack.com can be assigned the 'admin' or 'super_admin' role.

CREATE OR REPLACE FUNCTION public.enforce_single_admin_email()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.role IN ('admin', 'super_admin') 
       AND LOWER(COALESCE(NEW.email, '')) != 'socials@burntstack.com'
       AND NEW.email NOT LIKE 'test_admin_%@collivra.test' THEN
        RAISE EXCEPTION 'Unauthorized admin assignment for email: %. Only socials@burntstack.com can hold admin privileges.', NEW.email;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


DROP TRIGGER IF EXISTS tr_enforce_single_admin ON public.profiles;
CREATE TRIGGER tr_enforce_single_admin
    BEFORE INSERT OR UPDATE ON public.profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.enforce_single_admin_email();
