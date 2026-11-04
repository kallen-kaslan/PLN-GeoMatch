import { api } from "@/lib/api";

export type Role = "admin" | "analis" | "auditor";
export interface User { id: string; username: string; role: Role; is_active: boolean }
export interface AccountInput { username: string; password: string; role: Role; admin_password: string }
export interface AccountUpdate { role: Role; is_active: boolean; password?: string; admin_password: string }
export const sessionChannel = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel("geomatch-session") : null;
export const authApi = {
  login: async (username: string, password: string) => {
    const response = await api.post<User>("/auth/login", { username, password });
    sessionChannel?.postMessage("changed");
    return response.data;
  },
  me: async () => (await api.get<User>("/auth/me")).data,
  logout: async () => { await api.post("/auth/logout"); sessionChannel?.postMessage("changed"); },
  changePassword: async (current_password: string, new_password: string) => { await api.post("/auth/password", { current_password, new_password }); sessionChannel?.postMessage("changed"); },
  users: async () => (await api.get<User[]>("/admin/users")).data,
  createUser: async (input: AccountInput) => (await api.post<User>("/admin/users", input)).data,
  updateUser: async (id: string, input: AccountUpdate) => (await api.patch<User>(`/admin/users/${id}`, input)).data,
};
