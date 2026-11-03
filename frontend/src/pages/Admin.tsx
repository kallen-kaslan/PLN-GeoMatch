import { MetricCard } from "@/components/data/MetricCard";
import { useState, useEffect, useCallback } from "react";
import { useAppStore } from "@/store/app";
import { supabase } from "@/lib/supabase";
import { UserCog, Shield, Trash2, Search, Mail, Calendar, UserPlus, CheckCircle, XCircle } from "lucide-react";

interface RealUser {
  id: string;
  username: string;
  email?: string;
  role: "admin" | "auditor" | "analis";
  status?: string;
  created_at?: string;
  updated_at: string | null;
}

function formatDate(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleDateString("id-ID");
}

export default function AdminPage() {
  const { user } = useAppStore();
  const [users, setUsers] = useState<RealUser[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [newAdminEmail, setNewAdminEmail] = useState("");
  const [newAdminPassword, setNewAdminPassword] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);
  const [formError, setFormError] = useState("");

  const loadUsers = useCallback(async () => {
    setLoading(true);
    const { data, error } = await supabase.from("profiles").select("*");
    if (error) {
      console.error("Gagal memuat profil:", error);
    } else if (data) {
      setUsers(data as RealUser[]);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const handleUpdateRole = async (userId: string, newRole: "admin" | "auditor" | "analis") => {
    if (!window.confirm(`Ubah role user ini menjadi ${newRole}?`)) return;
    setActionLoading(userId);
    const { error } = await supabase.from("profiles").update({ role: newRole }).eq("id", userId);
    if (error) {
      alert("Gagal mengubah role: " + error.message);
    } else {
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, role: newRole } : u)));
    }
    setActionLoading(null);
  };

  const getNextRole = (current: "admin" | "auditor" | "analis"): "admin" | "auditor" | "analis" => {
    if (current === "admin") return "auditor";
    if (current === "auditor") return "analis";
    return "admin";
  };

  const getRoleBadgeClass = (role: "admin" | "auditor" | "analis") => {
    switch (role) {
      case "admin":
        return "bg-[#2563eb] text-white border-[#1e40af]";
      case "auditor":
        return "bg-[#7c3aed] text-white border-[#5b21b6]";
      case "analis":
        return "bg-[#059669] text-white border-[#047857]";
      default:
        return "bg-gray-500 text-white border-gray-700";
    }
  };

  const handleDeleteUser = async (userId: string, username: string) => {
    if (!window.confirm(`HAPUS PERMANEN user "${username}"? Tindakan ini tidak bisa dibatalkan!`)) return;
    setActionLoading(userId);
    const { error } = await supabase.from("profiles").delete().eq("id", userId);
    if (error) {
      alert("Gagal menghapus user: " + error.message);
    } else {
      setUsers((prev) => prev.filter((u) => u.id !== userId));
    }
    setActionLoading(null);
  };

  const handleAddAdmin = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    if (!newAdminEmail || !newAdminPassword) return;

    setActionLoading("new");
    const { data, error } = await supabase.auth.signUp({
      email: newAdminEmail,
      password: newAdminPassword,
      options: { data: { username: newAdminEmail.split("@")[0] } }
    });

    if (error) {
      setFormError(error.message);
    } else if (data.user) {
      // Role default 'admin' sudah diatur oleh trigger database
      setNewAdminEmail("");
      setNewAdminPassword("");
      setShowAddForm(false);
      loadUsers();
    }
    setActionLoading(null);
  };

  const filteredUsers = users.filter((u) =>
    (u.username || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
    (u.email || "").toLowerCase().includes(searchQuery.toLowerCase())
  );

  const stats = {
    total: users.length,
    admins: users.filter((u) => u.role === "admin").length,
    auditors: users.filter((u) => u.role === "auditor").length,
    analysts: users.filter((u) => u.role === "analis").length,
  };

  // Hanya admin yang boleh mengelola akun pengguna
  if (user?.role !== "admin") {
    return (
      <div className="p-6 border border-ui-border rounded-lg bg-white ">
        <div className="text-center py-10 sm:py-16">
          <Shield className="w-16 h-16 text-[#dc2626] mx-auto mb-4" />
          <h2 className="text-xl sm:text-2xl font-semibold text-[#dc2626] mb-2">Akses Ditolak</h2>
          <p className="text-sm text-ui-muted">Halaman ini hanya untuk pengguna dengan hak akses Administrator.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold mb-1 flex items-center gap-2">
            <UserCog className="w-6 h-6 sm:w-7 sm:h-7" strokeWidth={2.5} />
            Manajemen Pengguna
          </h1>
          <p className="text-xs sm:text-sm text-ui-muted">
            Kelola akun, role, dan hak akses pengguna sistem PLN GeoMatch
          </p>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="geo-metrics geo-metrics-4">
        <MetricCard label="Total Pengguna" value={stats.total} tone="primary" />
        <MetricCard label="Admin" value={stats.admins} tone="violet" icon={Shield} />
        <MetricCard label="Auditor" value={stats.auditors} tone="warning" />
        <MetricCard label="Analis" value={stats.analysts} tone="success" />
      </div>

      {/* Add Admin Form */}
      <div className="flex justify-end">
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="flex items-center gap-2 px-4 py-2 border-2 border-neo-black bg-neo-black text-white rounded text-sm font-bold shadow-[3px_3px_0_#6B82CB] hover:translate-y-0.5 active:translate-y-1 transition-all"
        >
          <UserPlus size={18} />
          {showAddForm ? "Batal" : "Tambah Admin Baru"}
        </button>
      </div>

      {showAddForm && (
        <form onSubmit={handleAddAdmin} className="p-4 border-2 border-neo-black bg-white rounded-sm shadow-[4px_4px_0_#0a0a0a] space-y-4">
          <h3 className="font-black text-lg">Registrasi Admin Baru</h3>
          {formError && <div className="text-red-600 text-xs font-bold bg-red-50 p-2 border border-red-200">{formError}</div>}
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold mb-1">Email</label>
              <input
                type="email"
                required
                value={newAdminEmail}
                onChange={(e) => setNewAdminEmail(e.target.value)}
                className="w-full border-2 border-neo-border p-2 text-sm focus:outline-none focus:border-neo-black"
                placeholder="admin@pln.co.id"
              />
            </div>
            <div>
              <label className="block text-xs font-bold mb-1">Password</label>
              <input
                type="password"
                required
                value={newAdminPassword}
                onChange={(e) => setNewAdminPassword(e.target.value)}
                className="w-full border-2 border-neo-border p-2 text-sm focus:outline-none focus:border-neo-black"
                placeholder="Minimal 6 karakter"
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={actionLoading === "new"}
            className="px-6 py-2 bg-neo-black text-white font-bold text-sm border-2 border-neo-black hover:bg-neutral-800 disabled:opacity-50"
          >
            {actionLoading === "new" ? "Memproses..." : "Simpan Admin"}
          </button>
        </form>
      )}

      {/* Search Bar */}
      <div className="p-3.5 sm:p-4 border border-ui-border rounded-lg bg-white ">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#666]" strokeWidth={2} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Cari username atau email..."
            className="mobile-input w-full border border-ui-border pl-11 pr-4 py-2.5 rounded-lg font-semibold text-sm focus:outline-none focus:ring-2 focus:ring-neo-accent"
          />
        </div>
      </div>

      {/* Users View */}
      {loading ? (
        <div className="p-8 text-center text-sm font-semibold text-ui-muted border border-dashed border-ui-border rounded-lg bg-white">
          Memuat data pengguna...
        </div>
      ) : (
        <>
          {/* Mobile Card List (< md) */}
          <div className="block md:hidden space-y-3">
            {filteredUsers.map((u) => (
              <div
                key={u.id}
                className="border border-neo-black rounded-lg bg-white p-4  space-y-3"
              >
                <div className="flex items-start justify-between gap-2 border-b border-ui-border pb-2.5">
                  <div>
                    <h3 className="text-sm font-semibold text-neo-black flex items-center gap-1.5">
                      <UserCog className="w-4 h-4 text-gray-500" />
                      {u.username}
                    </h3>
                    <p className="text-xs text-gray-600 flex items-center gap-1 mt-0.5">
                      <Mail className="w-3 h-3 text-gray-400" />
                      {u.email || "Email tidak tersedia"}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 px-2 py-0.5 rounded text-xs font-semibold border ${getRoleBadgeClass(u.role)}`}
                  >
                    {u.role.toUpperCase()}
                  </span>
                </div>

                <div className="flex items-center justify-between text-xs">
                  <span className="text-gray-500 text-xs flex items-center gap-1 font-mono">
                    <Calendar className="w-3 h-3" />
                    {formatDate(u.updated_at)}
                  </span>
                </div>

                <div className="pt-2 border-t border-ui-border flex items-center gap-2">
                  <button
                    onClick={() => handleUpdateRole(u.id, getNextRole(u.role))}
                    disabled={actionLoading === u.id || u.id === user.id}
                    className="touch-min flex-1 flex items-center justify-center gap-1.5 px-3 py-2 border border-ui-border bg-white text-neo-black rounded text-xs font-semibold disabled:opacity-50"
                  >
                    <Shield className="w-3.5 h-3.5" />
                    Ganti Role
                  </button>
                  <button
                    onClick={() => handleDeleteUser(u.id, u.username)}
                    disabled={actionLoading === u.id || u.id === user.id}
                    className="touch-min flex-1 flex items-center justify-center gap-1.5 px-3 py-2 border border-[#dc2626] bg-white text-[#dc2626] rounded text-xs font-semibold   disabled:opacity-50 disabled:cursor-not-allowed"
                    title={u.id === user.id ? "Tidak bisa hapus akun sendiri" : "Hapus user"}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Hapus
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Desktop Table View (>= md) */}
          <div className="hidden md:block border border-ui-border rounded-lg bg-white  overflow-x-auto neo-scrollbar">
            <table className="w-full text-left text-[13px] border-collapse min-w-[700px]">
              <thead className="bg-ui-table-head text-neo-black border-b border-ui-border">
                <tr>
                  <th className="p-3 border-r border-ui-border font-semibold">Username</th>
                  <th className="p-3 border-r border-ui-border font-semibold">Email</th>
                  <th className="p-3 border-r border-ui-border font-semibold">Role</th>
                  <th className="p-3 border-r border-ui-border font-semibold">Terdaftar</th>
                  <th className="p-3 text-center font-semibold">Aksi</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map((u) => (
                  <tr key={u.id} className="border-b border-ui-border hover:bg-neo-white transition-colors">
                    <td className="p-3 border-r border-ui-border font-semibold">
                      <div className="flex items-center gap-2">
                        <UserCog className="w-4 h-4 text-[#666]" />
                        {u.username}
                      </div>
                    </td>
                    <td className="p-3 border-r border-ui-border text-[#666]">{u.email}</td>
                    <td className="p-3 border-r border-ui-border">
                      <span
                        className={`px-2 py-1 rounded text-xs font-semibold border ${
                          u.role === "admin"
                            ? "bg-[#2563eb] text-white border-[#1e40af]"
                            : u.role === "analis"
                            ? "bg-[#16a34a] text-white border-[#15803d]"
                            : "bg-[#d97706] text-white border-[#b45309]"
                        }`}
                      >
                        {u.role.toUpperCase()}
                      </span>
                    </td>
                    <td className="p-3 border-r border-ui-border">
                      {u.status === "active" ? (
                        <span className="flex items-center gap-1 text-[#16a34a] font-semibold">
                          <CheckCircle className="w-4 h-4" />
                          Aktif
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-[#dc2626] font-semibold">
                          <XCircle className="w-4 h-4" />
                          Diblokir
                        </span>
                      )}
                    </td>
                    <td className="p-3 border-r border-ui-border text-[#666] font-mono text-xs">
                      {u.created_at ? new Date(u.created_at).toLocaleDateString("id-ID") : '-'}
                    </td>
                    <td className="p-3 text-center">
                      <div className="flex justify-center gap-2">
                        <button
                          onClick={() => handleUpdateRole(u.id, getNextRole(u.role))}
                          disabled={actionLoading === u.id || u.id === user.id}
                          className="touch-min flex-1 flex items-center justify-center gap-1.5 px-3 py-2 border border-ui-border bg-white text-neo-black rounded text-xs font-semibold disabled:opacity-50"
                        >
                          <Shield className="w-3 h-3 inline mr-1" />
                          Ganti Role
                        </button>
                        <button
                          onClick={() => handleDeleteUser(u.id, u.username)}
                          disabled={actionLoading === u.id || u.id === user.id}
                          className="touch-min px-3 py-1.5 border border-[#dc2626] bg-white text-[#dc2626] rounded text-xs font-semibold  hover:bg-[#fee2e2] hover:-translate-y-0.5  transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                          title={u.id === user.id ? "Tidak bisa hapus akun sendiri" : "Hapus user"}
                        >
                          <Trash2 className="w-3 h-3 inline mr-1" />
                          Hapus
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {filteredUsers.length === 0 && !loading && (
        <div className="p-8 border border-dashed border-ui-border rounded-lg text-center text-sm text-[#666] bg-white">
          Tidak ada user yang sesuai dengan pencarian.
        </div>
      )}

      {/* Info Footer */}
      <div className="p-4 border border-[#2563eb] bg-[#dbeafe] rounded-lg text-xs text-[#1e40af]">
        <p className="font-semibold mb-1">ℹ️ Informasi Admin:</p>
        <ul className="list-disc list-inside space-y-1 text-[#1e40af]/80">
          <li>Halaman ini untuk manajemen akun (Admin, Auditor, Analis).</li>
          <li>Tombol 'Ganti Role' akan merotasi role user (Admin &rarr; Auditor &rarr; Analis &rarr; Admin).</li>
          <li>Penghapusan user bersifat permanen dan tidak dapat dibatalkan.</li>
          <li>Admin tidak dapat menghapus akun sendiri.</li>
        </ul>
      </div>
    </div>
  );
}
