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
  isMobileMenuOpen: boolean;
  isSidebarCollapsed: boolean;
  setUser: (u: User | null) => void;
  setToken: (t: string | null) => void;
  setTheme: (t: "light" | "dark") => void;
  setActiveProcessId: (id: string | null) => void;
  setIsMobileMenuOpen: (open: boolean) => void;
  toggleMobileMenu: () => void;
  setIsSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebarCollapsed: () => void;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
};

const getInitialSidebarCollapsed = (): boolean => {
  try {
    return localStorage.getItem("pln_geomatch_sidebar_collapsed") === "true";
  } catch {
    return false;
  }
};

export const useAppStore = create<AppState>((set) => ({
  user: null,
  token: null,
  theme: "light",
  activeProcessId: null,
  isMobileMenuOpen: false,
  isSidebarCollapsed: getInitialSidebarCollapsed(),
  setUser: (u) => set({ user: u }),
  setToken: (t) => set({ token: t }),
  setTheme: (t) => set({ theme: t }),
  setActiveProcessId: (id) => set({ activeProcessId: id }),
  setIsMobileMenuOpen: (open) => set({ isMobileMenuOpen: open }),
  toggleMobileMenu: () => set((state) => ({ isMobileMenuOpen: !state.isMobileMenuOpen })),
  setIsSidebarCollapsed: (collapsed) => {
    try {
      localStorage.setItem("pln_geomatch_sidebar_collapsed", String(collapsed));
    } catch {
      // Ignore localStorage errors
    }
    set({ isSidebarCollapsed: collapsed });
  },
  toggleSidebarCollapsed: () =>
    set((state) => {
      const next = !state.isSidebarCollapsed;
      try {
        localStorage.setItem("pln_geomatch_sidebar_collapsed", String(next));
      } catch {
        // Ignore localStorage errors
      }
      return { isSidebarCollapsed: next };
    }),
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
  logout: () => set({ user: null, token: null, activeProcessId: null, isMobileMenuOpen: false }),
}));
