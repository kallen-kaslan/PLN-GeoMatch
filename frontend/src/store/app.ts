import { create } from "zustand";
import { authApi, type User } from "@/lib/accounts";
import { queryClient } from "@/lib/queryClient";
import type { ApiError } from "@/lib/api";
export type { Role, User } from "@/lib/accounts";

export type AppState = {
  user: User | null;
  authStatus: "checking" | "authenticated" | "anonymous" | "error";
  authError: string;
  authNotice: string;
  theme: "light" | "dark";
  activeProcessId: string | null;
  isMobileMenuOpen: boolean;
  isSidebarCollapsed: boolean;
  initialize: () => Promise<void>;
  endSession: (message?: string) => void;
  setTheme: (t: "light" | "dark") => void;
  setActiveProcessId: (id: string | null) => void;
  setIsMobileMenuOpen: (open: boolean) => void;
  toggleMobileMenu: () => void;
  setIsSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebarCollapsed: () => void;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const getInitialSidebarCollapsed = (): boolean => {
  try {
    return localStorage.getItem("pln_geomatch_sidebar_collapsed") === "true";
  } catch {
    return false;
  }
};

let initialization: Promise<void> | null = null;

function clearPrivateCache() {
  void queryClient.cancelQueries();
  queryClient.clear();
}

export const useAppStore = create<AppState>((set, get) => ({
  user: null,
  authStatus: "checking",
  authError: "",
  authNotice: "",
  theme: "light",
  activeProcessId: null,
  isMobileMenuOpen: false,
  isSidebarCollapsed: getInitialSidebarCollapsed(),
  initialize: () => {
    if (initialization) return initialization;
    set({ authStatus: "checking", authError: "" });
    initialization = authApi.me().then((user) => {
      set({ user, authStatus: "authenticated", authNotice: "" });
    }).catch((error: ApiError) => {
      if (error.status === 401) get().endSession();
      else set({ user: null, authStatus: "error", authError: error.message });
    }).finally(() => { initialization = null; });
    return initialization;
  },
  endSession: (message = "") => {
    set({ user: null, authStatus: "anonymous", authError: "", authNotice: message || get().authNotice, activeProcessId: null, isMobileMenuOpen: false });
    clearPrivateCache();
  },
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
  login: async (username, password) => {
    const user = await authApi.login(username, password);
    clearPrivateCache();
    set({ user, authStatus: "authenticated", authError: "", authNotice: "" });
  },
  logout: async () => {
    try { await authApi.logout(); }
    catch (error) { if ((error as ApiError).status !== 401) throw error; }
    get().endSession();
  },
}));
