import { create } from "zustand";

export type Role = "admin" | "analis" | "auditor";

export type User = {
  id: string;
  username: string;
  role: Role;
};

export type AppState = {
  user: User | null;
  token: string | null;
  theme: "light" | "dark";
  activeProcessId: string | null;
  setUser: (u: User | null) => void;
  setToken: (t: string | null) => void;
  setTheme: (t: "light" | "dark") => void;
  setActiveProcessId: (id: string | null) => void;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
};

export const useAppStore = create<AppState>((set) => ({
  user: null,
  token: null,
  theme: "light",
  activeProcessId: null,
  setUser: (u) => set({ user: u }),
  setToken: (t) => set({ token: t }),
  setTheme: (t) => set({ theme: t }),
  setActiveProcessId: (id) => set({ activeProcessId: id }),
  login: async (username, _password) => {
    // Phase 1 scaffold: mock login until backend auth is ready (Phase 1C+).
    // Mock user roles based on username
    let role: Role = "analis";
    if (username.toLowerCase() === "admin") {
      role = "admin";
    } else if (username.toLowerCase().includes("audit")) {
      role = "auditor";
    }

    const mockUser: User = { id: `u_${Date.now()}`, username, role };
    const mockToken = `mock-token-${Date.now()}`;
    set({ user: mockUser, token: mockToken });
  },
  logout: () => set({ user: null, token: null, activeProcessId: null }),
}));
