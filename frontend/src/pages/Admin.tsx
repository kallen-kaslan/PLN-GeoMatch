import { TablePagination } from "@/components/data/TablePagination";
import { MetricCard } from "@/components/data/MetricCard";
import { useState, useEffect, useCallback } from "react";
import { useAppStore } from "@/store/app";
import { UserCog, Shield, Ban, Trash2, CheckCircle, XCircle, Search, Mail, Calendar } from "lucide-react";

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
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const loadUsers = useCallback(() => {
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
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

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

  const activePage = Math.min(page, Math.max(1, Math.ceil(filteredUsers.length / pageSize)));
  const pageRows = filteredUsers.slice((activePage - 1) * pageSize, activePage * pageSize);

  const stats = {
    total: users.length,
    active: users.filter((u) => u.status === "active").length,
    blocked: users.filter((u) => u.status === "blocked").length,
    admins: users.filter((u) => u.role === "admin").length,
  };

  // Check if current user is admin
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
        <MetricCard label="Total User" value={stats.total} tone="primary" />
        <MetricCard label="Aktif" value={stats.active} tone="success" />
        <MetricCard label="Diblokir" value={stats.blocked} tone="danger" />
        <MetricCard label="Admin" value={stats.admins} tone="violet" icon={Shield} />
      </div>

      {/* Search Bar */}
      <div className="p-3.5 sm:p-4 border border-ui-border rounded-lg bg-white ">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#666]" strokeWidth={2} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); setPage(1); }}
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
            {pageRows.map((u) => (
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
                      {u.email}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 px-2 py-0.5 rounded text-xs font-semibold border ${
                      u.role === "admin"
                        ? "bg-[#2563eb] text-white border-[#1e40af]"
                        : u.role === "analis"
                        ? "bg-[#16a34a] text-white border-[#15803d]"
                        : "bg-[#d97706] text-white border-[#b45309]"
                    }`}
                  >
                    {u.role.toUpperCase()}
                  </span>
                </div>

                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-1.5">
                    {u.status === "active" ? (
                      <span className="flex items-center gap-1 text-[#16a34a] font-semibold">
                        <CheckCircle className="w-3.5 h-3.5" />
                        Aktif
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-[#dc2626] font-semibold">
                        <XCircle className="w-3.5 h-3.5" />
                        Diblokir
                      </span>
                    )}
                  </div>
                  <span className="text-gray-500 text-xs flex items-center gap-1 font-mono">
                    <Calendar className="w-3 h-3" />
                    {new Date(u.created_at).toLocaleDateString("id-ID")}
                  </span>
                </div>

                <div className="pt-2 border-t border-ui-border flex items-center gap-2">
                  <button
                    onClick={() => handleBlockUser(u.id, u.status)}
                    disabled={actionLoading === u.id}
                    className={`touch-min flex-1 flex items-center justify-center gap-1.5 px-3 py-2 border rounded text-xs font-semibold   disabled:opacity-50 ${
                      u.status === "active"
                        ? "border-[#d97706] bg-[#fef3c7] text-[#92400e]"
                        : "border-[#16a34a] bg-[#dcfce7] text-[#15803d]"
                    }`}
                  >
                    <Ban className="w-3.5 h-3.5" />
                    {u.status === "active" ? "Blokir" : "Aktifkan"}
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
                  <th className="p-3 border-r border-ui-border font-semibold">Status</th>
                  <th className="p-3 border-r border-ui-border font-semibold">Terdaftar</th>
                  <th className="p-3 text-center font-semibold">Aksi</th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map((u) => (
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
                      {new Date(u.created_at).toLocaleDateString("id-ID")}
                    </td>
                    <td className="p-3 text-center">
                      <div className="flex justify-center gap-2">
                        <button
                          onClick={() => handleBlockUser(u.id, u.status)}
                          disabled={actionLoading === u.id}
                          className={`touch-min px-3 py-1.5 border rounded text-xs font-semibold  hover:-translate-y-0.5  transition-all disabled:opacity-50 ${
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

      <TablePagination context="pengguna" page={activePage} pageSize={pageSize} total={loading ? undefined : filteredUsers.length} loading={loading} onPageChange={setPage} onPageSizeChange={(size) => { setPageSize(size); setPage(1); }} />
      {/* Info Footer */}
      <div className="p-4 border border-[#2563eb] bg-[#dbeafe] rounded-lg text-xs text-[#1e40af]">
        <p className="font-semibold mb-1">ℹ️ Informasi Admin:</p>
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
