import { useState, useEffect } from "react";
import { useAppStore } from "@/store/app";
import { UserCog, Shield, Ban, Trash2, CheckCircle, XCircle, Search } from "lucide-react";

interface MockUser {
  id: string;
  username: string;
  email: string;
  role: "admin" | "analis" | "auditor";
  status: "active" | "blocked";
  created_at: string;
}

export default function AdminPage() {
  const { user } = useAppStore();
  const [users, setUsers] = useState<MockUser[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = () => {
    setLoading(true);
    // Mock data - replace with real API call
    setTimeout(() => {
      setUsers([
        { id: "u_1", username: "admin", email: "admin@pln.co.id", role: "admin", status: "active", created_at: "2026-01-15" },
        { id: "u_2", username: "petugas", email: "petugas@pln.co.id", role: "analis", status: "active", created_at: "2026-02-10" },
        { id: "u_3", username: "auditor1", email: "audit@pln.co.id", role: "auditor", status: "active", created_at: "2026-03-05" },
        { id: "u_4", username: "analis2", email: "analis2@pln.co.id", role: "analis", status: "blocked", created_at: "2026-01-20" },
      ]);
      setLoading(false);
    }, 500);
  };

  const handleBlockUser = async (userId: string, currentStatus: string) => {
    if (!window.confirm(`${currentStatus === "active" ? "Blokir" : "Aktifkan"} user ini?`)) return;

    setActionLoading(userId);
    // Mock action - replace with real API call
    setTimeout(() => {
      setUsers((prev) =>
        prev.map((u) =>
          u.id === userId ? { ...u, status: u.status === "active" ? "blocked" : "active" } : u
        )
      );
      setActionLoading(null);
    }, 300);
  };

  const handleDeleteUser = async (userId: string, username: string) => {
    if (!window.confirm(`HAPUS PERMANEN user "${username}"? Tindakan ini tidak bisa dibatalkan!`)) return;

    setActionLoading(userId);
    // Mock action - replace with real API call
    setTimeout(() => {
      setUsers((prev) => prev.filter((u) => u.id !== userId));
      setActionLoading(null);
    }, 300);
  };

  const filteredUsers = users.filter((u) =>
    u.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
    u.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const stats = {
    total: users.length,
    active: users.filter((u) => u.status === "active").length,
    blocked: users.filter((u) => u.status === "blocked").length,
    admins: users.filter((u) => u.role === "admin").length,
  };

  // Check if current user is admin
  if (user?.role !== "admin") {
    return (
      <div className="p-6 border border-neo-border rounded-sm bg-white shadow-[0_4px_0_#0a0a0a]">
        <div className="text-center py-12">
          <Shield className="w-16 h-16 text-[#dc2626] mx-auto mb-4" />
          <h2 className="text-xl font-bold text-[#dc2626] mb-2">Akses Ditolak</h2>
          <p className="text-sm text-neo-border">Halaman ini hanya untuk Administrator.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold mb-1 flex items-center gap-2">
            <UserCog className="w-7 h-7" strokeWidth={2.5} />
            Manajemen Pengguna
          </h1>
          <p className="text-sm text-neo-border">
            Kelola akses pengguna sistem PLN GeoMatch
          </p>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 border-3 border-neo-black rounded-lg bg-white shadow-[4px_4px_0_#0a0a0a]">
          <p className="text-xs text-[#666] font-bold mb-1">Total User</p>
          <p className="text-2xl font-black text-neo-black">{stats.total}</p>
        </div>
        <div className="p-4 border-3 border-[#16a34a] rounded-lg bg-[#dcfce7] shadow-[4px_4px_0_#16a34a]">
          <p className="text-xs text-[#16a34a] font-bold mb-1">Aktif</p>
          <p className="text-2xl font-black text-[#16a34a]">{stats.active}</p>
        </div>
        <div className="p-4 border-3 border-[#dc2626] rounded-lg bg-[#fee2e2] shadow-[4px_4px_0_#dc2626]">
          <p className="text-xs text-[#dc2626] font-bold mb-1">Diblokir</p>
          <p className="text-2xl font-black text-[#dc2626]">{stats.blocked}</p>
        </div>
        <div className="p-4 border-3 border-[#2563eb] rounded-lg bg-[#dbeafe] shadow-[4px_4px_0_#2563eb]">
          <p className="text-xs text-[#2563eb] font-bold mb-1">Admin</p>
          <p className="text-2xl font-black text-[#2563eb]">{stats.admins}</p>
        </div>
      </div>

      {/* Search Bar */}
      <div className="p-4 border border-neo-border rounded-sm bg-white shadow-[0_4px_0_#0a0a0a]">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#666]" strokeWidth={2} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Cari username atau email..."
            className="w-full border-2 border-neo-border pl-11 pr-4 py-2.5 rounded-sm font-semibold text-sm focus:outline-none focus:ring-2 focus:ring-neo-accent"
          />
        </div>
      </div>

      {/* Users Table */}
      {loading ? (
        <div className="p-8 text-center text-sm text-neo-border">Memuat data pengguna...</div>
      ) : (
        <div className="border border-neo-border rounded-sm bg-white shadow-[0_4px_0_#0a0a0a] overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-neo-black text-white border-b-2 border-neo-border">
              <tr>
                <th className="p-3 border-r border-neo-border font-black">Username</th>
                <th className="p-3 border-r border-neo-border font-black">Email</th>
                <th className="p-3 border-r border-neo-border font-black">Role</th>
                <th className="p-3 border-r border-neo-border font-black">Status</th>
                <th className="p-3 border-r border-neo-border font-black">Terdaftar</th>
                <th className="p-3 text-center font-black">Aksi</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((u) => (
                <tr key={u.id} className="border-b border-neo-border hover:bg-neo-white">
                  <td className="p-3 border-r border-neo-border font-bold">
                    <div className="flex items-center gap-2">
                      <UserCog className="w-4 h-4 text-[#666]" />
                      {u.username}
                    </div>
                  </td>
                  <td className="p-3 border-r border-neo-border text-[#666]">{u.email}</td>
                  <td className="p-3 border-r border-neo-border">
                    <span
                      className={`px-2 py-1 rounded text-[10px] font-black border-2 ${
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
                  <td className="p-3 border-r border-neo-border">
                    {u.status === "active" ? (
                      <span className="flex items-center gap-1 text-[#16a34a] font-bold">
                        <CheckCircle className="w-4 h-4" />
                        Aktif
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-[#dc2626] font-bold">
                        <XCircle className="w-4 h-4" />
                        Diblokir
                      </span>
                    )}
                  </td>
                  <td className="p-3 border-r border-neo-border text-[#666] font-mono text-[11px]">
                    {new Date(u.created_at).toLocaleDateString("id-ID")}
                  </td>
                  <td className="p-3 text-center">
                    <div className="flex justify-center gap-2">
                      <button
                        onClick={() => handleBlockUser(u.id, u.status)}
                        disabled={actionLoading === u.id}
                        className={`px-3 py-1.5 border-2 rounded text-[11px] font-bold shadow-[2px_2px_0_#0a0a0a] hover:-translate-y-0.5 transition-all disabled:opacity-50 ${
                          u.status === "active"
                            ? "border-[#d97706] bg-[#fef3c7] text-[#92400e] hover:bg-[#fde68a]"
                            : "border-[#16a34a] bg-[#dcfce7] text-[#15803d] hover:bg-[#bbf7d0]"
                        }`}
                      >
                        <Ban className="w-3 h-3 inline mr-1" />
                        {u.status === "active" ? "Blokir" : "Aktifkan"}
                      </button>
                      <button
                        onClick={() => handleDeleteUser(u.id, u.username)}
                        disabled={actionLoading === u.id || u.id === user.id}
                        className="px-3 py-1.5 border-2 border-[#dc2626] bg-white text-[#dc2626] rounded text-[11px] font-bold shadow-[2px_2px_0_#dc2626] hover:bg-[#fee2e2] hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
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
      )}

      {filteredUsers.length === 0 && !loading && (
        <div className="p-8 border border-dashed border-neo-border rounded-sm text-center text-sm text-[#666]">
          Tidak ada user yang sesuai dengan pencarian.
        </div>
      )}

      {/* Info Footer */}
      <div className="p-4 border border-[#2563eb] bg-[#dbeafe] rounded-sm text-xs text-[#1e40af]">
        <p className="font-bold mb-1">ℹ️ Informasi Admin:</p>
        <ul className="list-disc list-inside space-y-1 text-[#1e40af]/80">
          <li>User yang diblokir tidak dapat login ke sistem</li>
          <li>Penghapusan user bersifat permanen dan tidak dapat dibatalkan</li>
          <li>Admin tidak dapat menghapus akun sendiri</li>
          <li>Phase 1: Mock data (Backend RBAC akan diimplementasikan pada Phase 1C+)</li>
        </ul>
      </div>
    </div>
  );
}
