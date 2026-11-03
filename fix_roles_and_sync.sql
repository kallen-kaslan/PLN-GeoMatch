-- 1. Bersihkan role yang tidak valid dan set ke default 'admin' jika tidak dikenal
UPDATE public.profiles
SET role = 'admin'
WHERE role NOT IN ('super_admin', 'admin');

-- 2. Update constraint role agar hanya menerima super_admin dan admin
ALTER TABLE public.profiles
DROP CONSTRAINT IF EXISTS profiles_role_check;

ALTER TABLE public.profiles
ADD CONSTRAINT profiles_role_check
CHECK (role IN ('super_admin', 'admin'));

-- 3. Fungsi untuk sinkronisasi role dari auth.users ke public.profiles
CREATE OR REPLACE FUNCTION public.sync_user_role()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE public.profiles
  SET role = COALESCE(NEW.raw_app_meta_data->>'role', 'admin')
  WHERE id = NEW.id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 4. Trigger saat auth.users diupdate (misal saat kita ganti role via SQL/Dashboard)
DROP TRIGGER IF EXISTS on_auth_user_updated ON auth.users;
CREATE TRIGGER on_auth_user_updated
  AFTER UPDATE OF raw_app_meta_data ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.sync_user_role();

-- 5. Perbaiki trigger pendaftaran agar default ke 'admin' (atau sesuai metadata jika ada)
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, username, role)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'username', split_part(NEW.email, '@', 1)),
    COALESCE(NEW.raw_app_meta_data->>'role', 'admin')
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 6. SQL Helper untuk Anda gunakan di Dashboard saat ingin mengubah role:
-- UPDATE auth.users SET raw_app_meta_data = raw_app_meta_data || '{"role": "super_admin"}' WHERE email = 'USER_EMAIL';
