import { StatusBadge } from "@/components/data/StatusBadge";
import { WorkspaceHeader, SectionHeading } from "@/components/layout/WorkspaceHeader";
import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle, Plus, Search, Shield, UserCog, X } from "lucide-react";
import { authApi, type Role, type User } from "@/lib/accounts";
import type { ApiError } from "@/lib/api";
import { buttonClass } from "@/lib/button";
import { useAppStore } from "@/store/app";

const control = "w-full rounded-lg border border-ui-border bg-white px-3 py-2 text-sm";
const roleLabels: Record<Role, string> = { admin: "Administrator", analis: "Analis", auditor: "Auditor (baca saja)" };

function AccountForm({ target, onClose, onSaved }: { target: User | null; onClose: () => void; onSaved: () => void }) {
  const [username, setUsername] = useState(target?.username ?? "");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [role, setRole] = useState<Role>(target?.role ?? "analis");
  const [active, setActive] = useState(target?.is_active ?? true);
  const save = useMutation({
    mutationFn: async () => {
      if ((!target || password) && password !== confirmation) throw new Error("Konfirmasi password tidak sama.");
      if (target) return authApi.updateUser(target.id, { role, is_active: active, admin_password: adminPassword, ...(password ? { password } : {}) });
      return authApi.createUser({ username, password, role, admin_password: adminPassword });
    },
    onSuccess: () => { setPassword(""); setConfirmation(""); setAdminPassword(""); onSaved(); },
    onError: () => setAdminPassword(""),
  });
  const submit = (event: FormEvent) => { event.preventDefault(); if (!save.isPending) save.mutate(); };
  return <section className="geo-panel max-w-3xl space-y-4 p-5" aria-label={target ? "Ubah pengguna" : "Tambah pengguna"}>
    <div className="flex items-center justify-between gap-3"><h2 className="font-semibold">{target ? "Ubah pengguna " + target.username : "Tambah pengguna"}</h2><button type="button" disabled={save.isPending} onClick={onClose} aria-label="Tutup formulir pengguna"><X size={20} /></button></div>
    <form onSubmit={submit} className="space-y-4">
      <fieldset disabled={save.isPending} className="grid gap-4 md:grid-cols-2">
        <label className="space-y-1 text-sm font-semibold">Username<input required readOnly={!!target} value={username} onChange={(event) => setUsername(event.target.value)} autoCapitalize="none" autoComplete="off" minLength={3} maxLength={64} pattern="[a-zA-Z0-9][a-zA-Z0-9._-]{2,63}" className={control} /></label>
        <label className="space-y-1 text-sm font-semibold">Peran<select value={role} onChange={(event) => setRole(event.target.value as Role)} className={control}>{Object.entries(roleLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
        <label className="space-y-1 text-sm font-semibold">{target ? "Password baru (opsional)" : "Password pengguna"}<input type="password" autoComplete="new-password" required={!target} minLength={15} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} className={control} /></label>
        <label className="space-y-1 text-sm font-semibold">Konfirmasi password pengguna<input type="password" autoComplete="new-password" required={!target || !!password} minLength={15} maxLength={128} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} className={control} /></label>
        {target && <label className="flex items-center gap-2 text-sm font-semibold"><input type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} />Akun aktif</label>}
        <label className="space-y-1 text-sm font-semibold md:col-span-2">Password admin Anda<input type="password" autoComplete="current-password" required maxLength={128} value={adminPassword} onChange={(event) => setAdminPassword(event.target.value)} className={control} /></label>
        <div className="flex flex-wrap gap-2 md:col-span-2"><button type="submit" className={buttonClass.primary}>{save.isPending && <LoaderCircle size={16} className="animate-spin" />}{target ? "Simpan perubahan pengguna" : "Buat pengguna"}</button><button type="button" onClick={onClose} className={buttonClass.secondary}>Batal</button></div>
      </fieldset>
      <p className="text-xs text-ui-muted">Gunakan passphrase 15–128 karakter. Perubahan role, status, atau password mencabut seluruh sesi pengguna tersebut.</p>
      {save.error && <p role="alert" className="text-sm text-red-700">{(save.error as ApiError).message}</p>}
    </form>
  </section>;
}

export default function AdminPage() {
  const user = useAppStore((state) => state.user);
  const client = useQueryClient();
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<User | null | undefined>(undefined);
  const [notice, setNotice] = useState("");
  const users = useQuery({ queryKey: ["admin", "users"], queryFn: authApi.users, enabled: user?.role === "admin", staleTime: 0 });
  if (user?.role !== "admin") return <div role="alert" className="geo-panel space-y-3 p-6"><Shield size={32} /><h1 className="text-xl font-semibold">Akses Ditolak</h1><p>Manajemen pengguna hanya tersedia untuk administrator.</p></div>;
  const filtered = users.data?.filter((item) => item.username.toLowerCase().includes(search.toLowerCase())) ?? [];
  return <div className="space-y-5">
    <WorkspaceHeader icon={UserCog} eyebrow="Administrasi" title={"Manajemen Pengguna"} description="Kelola akun, peran, dan akses pengguna ke ruang kerja." actions={<button type="button" className={buttonClass.primary} onClick={() => { setEditing(null); setNotice(""); }}><Plus size={16} />Tambah pengguna</button>} />
    {notice && <p role="status" className="rounded-lg bg-green-50 p-3 text-sm text-green-800">{notice}</p>}
    {editing !== undefined && <AccountForm key={editing?.id ?? "new"} target={editing} onClose={() => setEditing(undefined)} onSaved={() => { setEditing(undefined); setNotice("Pengguna berhasil disimpan."); void client.invalidateQueries({ queryKey: ["admin", "users"] }); }} />}
    <section className="geo-panel space-y-4 p-4 sm:p-5"><SectionHeading icon={UserCog} title="Daftar pengguna" />
    <label className="flex max-w-md items-center gap-2"><Search size={18} /><input aria-label="Cari pengguna" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Cari username" className={control} /></label>
    {users.isPending && <p role="status" className="flex items-center gap-2"><LoaderCircle size={18} className="animate-spin" />Memuat pengguna...</p>}
    {users.isError && <p role="alert" className="text-red-700">{(users.error as ApiError).message}</p>}
    {users.data && <p className="text-xs text-ui-muted sm:hidden">Geser tabel untuk melihat peran, status, dan tindakan.</p>}
    {users.data && <div className="geo-panel overflow-x-auto"><table className="w-full text-left text-sm"><thead className="border-b border-ui-border bg-ui-table-head"><tr><th className="p-3">Username</th><th className="p-3">Peran</th><th className="p-3">Status</th><th className="p-3">Tindakan</th></tr></thead><tbody>{filtered.map((item) => <tr key={item.id} className="border-b border-ui-border"><td className="p-3">{item.username}{item.id === user.id && <><span className="text-ui-muted"> (Anda)</span><p className="mt-1 text-xs text-ui-muted">Ubah kata sandi melalui menu akun.</p></>}</td><td className="p-3">{roleLabels[item.role]}</td><td className="p-3"><StatusBadge tone={item.is_active ? "success" : "neutral"}>{item.is_active ? "Aktif" : "Nonaktif"}</StatusBadge></td><td className="p-3"><button type="button" disabled={item.id === user.id} aria-label={"Ubah pengguna " + item.username} onClick={() => { setEditing(item); setNotice(""); }} className={buttonClass.secondary}>Ubah / reset password</button></td></tr>)}</tbody></table>{!filtered.length && <p className="p-4 text-sm">Tidak ada pengguna sesuai pencarian.</p>}</div>}
    </section>
  </div>;
}
