-- ==============================================================================
-- SETUP SKEMA SUPABASE UNTUK PLN GEOMATCH (3 ROLE: admin, auditor, analis)
-- Jalankan skrip ini SEKALI di: Supabase Dashboard -> SQL Editor -> Run
-- ==============================================================================

-- 1. Buat tabel public.profiles jika belum ada
CREATE TABLE IF NOT EXISTS public.profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  username TEXT,
  role TEXT NOT NULL DEFAULT 'analis' CHECK (role IN ('admin', 'auditor', 'analis')),
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tambahkan kolom jika tabel sudah sempat dibuat sebelumnya
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active';
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- 2. Aktifkan Row Level Security (RLS)
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- 3. Hapus policy lama agar bersih
DROP POLICY IF EXISTS "Profiles are viewable by owner" ON public.profiles;
DROP POLICY IF EXISTS "Admins can view all profiles" ON public.profiles;
DROP POLICY IF EXISTS "Super admins can update profiles" ON public.profiles;
DROP POLICY IF EXISTS "Admins can update profiles" ON public.profiles;
DROP POLICY IF EXISTS "Admins can delete profiles" ON public.profiles;

-- 4. Pasang Policy RLS Baru
-- Setiap user bisa membaca profilnya sendiri
CREATE POLICY "Profiles are viewable by owner"
  ON public.profiles FOR SELECT
  USING ( auth.uid() = id );

-- Admin bisa melihat semua profil
CREATE POLICY "Admins can view all profiles"
  ON public.profiles FOR SELECT
  USING ( (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin' );

-- Admin bisa mengupdate profil & role user lain
CREATE POLICY "Admins can update profiles"
  ON public.profiles FOR UPDATE
  USING ( (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin' );

-- Admin bisa menghapus user dari profiles
CREATE POLICY "Admins can delete profiles"
  ON public.profiles FOR DELETE
  USING ( (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin' );

-- 5. Trigger Saat User Baru Terdaftar di Supabase Auth
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, username, role, status, created_at, updated_at)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'username', split_part(NEW.email, '@', 1)),
    COALESCE(NEW.raw_app_meta_data->>'role', 'analis'),
    'active',
    NOW(),
    NOW()
  )
  ON CONFLICT (id) DO UPDATE
  SET role = EXCLUDED.role,
      username = EXCLUDED.username;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 6. Trigger Sinkronisasi: Saat role di public.profiles diubah di UI Admin -> sync ke auth.users (app_metadata)
CREATE OR REPLACE FUNCTION public.sync_profile_role_to_auth()
RETURNS TRIGGER AS $$
BEGIN
  -- Hanya update auth.users jika nilainya benar-benar berbeda (cegah infinite loop)
  UPDATE auth.users
  SET raw_app_meta_data = COALESCE(raw_app_meta_data, '{}'::jsonb) || jsonb_build_object('role', NEW.role)
  WHERE id = NEW.id
    AND (raw_app_meta_data->>'role' IS DISTINCT FROM NEW.role);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_profile_role_updated ON public.profiles;
CREATE TRIGGER on_profile_role_updated
  AFTER UPDATE OF role ON public.profiles
  FOR EACH ROW
  WHEN (OLD.role IS DISTINCT FROM NEW.role)
  EXECUTE FUNCTION public.sync_profile_role_to_auth();

-- 7. Trigger Sinkronisasi: Jika role diubah langsung dari Supabase Dashboard auth.users -> sync ke public.profiles
CREATE OR REPLACE FUNCTION public.sync_auth_role_to_profile()
RETURNS TRIGGER AS $$
DECLARE
  v_role TEXT;
BEGIN
  v_role := COALESCE(NEW.raw_app_meta_data->>'role', 'analis');
  -- Hanya update public.profiles jika nilainya benar-benar berbeda (cegah infinite loop)
  UPDATE public.profiles
  SET role = v_role,
      updated_at = NOW()
  WHERE id = NEW.id
    AND role IS DISTINCT FROM v_role;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_updated ON auth.users;
CREATE TRIGGER on_auth_user_updated
  AFTER UPDATE OF raw_app_meta_data ON auth.users
  FOR EACH ROW
  WHEN (OLD.raw_app_meta_data->>'role' IS DISTINCT FROM NEW.raw_app_meta_data->>'role')
  EXECUTE FUNCTION public.sync_auth_role_to_profile();

-- 8. View untuk Admin melihat users (bypass auth.users RLS)
DROP VIEW IF EXISTS public.user_accounts CASCADE;
CREATE OR REPLACE VIEW public.user_accounts AS
SELECT
    u.id,
    u.email,
    p.username,
    p.role,
    p.status,
    p.created_at,
    p.updated_at
FROM auth.users u
JOIN public.profiles p ON p.id = u.id;

-- Berikan izin view kepada authenticated
GRANT SELECT ON public.user_accounts TO authenticated;

-- 9. Kunci Seluruh Tabel Operasional PLN dari Akses Langsung API Supabase (RLS Lockdown)
-- FastAPI backend terhubung via direct PostgreSQL (user postgres) yang otomatis bypass RLS.
-- Perintah ini memastikan siapapun yang memegang anon key di browser TIDAK BISA membaca data operasional via PostgREST.
DO $$
DECLARE
    tbl text;
BEGIN
    FOR tbl IN
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename != 'profiles'
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;', tbl);
        EXECUTE format('REVOKE ALL ON TABLE public.%I FROM anon, authenticated;', tbl);
    END LOOP;
END $$;

-- Berikan izin akses profiles HANYA untuk authenticated user (terikat policy RLS)
GRANT SELECT, UPDATE, DELETE ON public.profiles TO authenticated;
REVOKE ALL ON public.profiles FROM anon;

-- ==============================================================================
-- CARA MEMBUAT AKUN ADMIN PERTAMA KALI:
-- 1. Buka Supabase Dashboard -> Authentication -> Users -> Add User (Create user)
-- 2. Masukkan Email & Password
-- 3. Buka SQL Editor dan jalankan query berikut untuk memberikan role admin:
--
-- UPDATE auth.users
-- SET raw_app_meta_data = COALESCE(raw_app_meta_data, '{}'::jsonb) || '{"role": "admin"}'::jsonb
-- WHERE email = 'email_admin_anda@pln.co.id';
-- ==============================================================================
