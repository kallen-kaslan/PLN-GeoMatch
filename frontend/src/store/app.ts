import { create } from "zustand";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";

export type Role = "admin" | "auditor" | "analis";

const VALID_ROLES: readonly Role[] = ["admin", "auditor", "analis"];

function readRole(session: Session | null): Role {
  const raw = (session?.user?.app_metadata as Record<string, unknown> | undefined)?.role;
  if (typeof raw === "string" && (VALID_ROLES as readonly string[]).includes(raw)) {
    return raw as Role;
  }
  // Default aman non-privileged
  return "analis";
}

function readUsername(session: Session | null): string {
  const meta = session?.user?.user_metadata as Record<string, unknown> | undefined;
  const username = typeof meta?.username === "string" ? meta.username.trim() : "";
  if (username) return username;
  const email = session?.user?.email ?? "";
  return email.split("@")[0] || "Pengguna";
}

export type User = {
  id: string;
  username: string;
  role: Role;
};

export type AppState = {
  user: User | null;
  token: string | null;
  initialized: boolean;
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
  applySession: (session: Session | null) => void;
  initAuth: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const getInitialSidebarCollapsed = (): boolean => {
  try {
    return localStorage.getItem("pln_geomatch_sidebar_collapsed") === "true";
  } catch {
    return false;
  }
};

export const useAppStore = create<AppState>((set, get) => ({
  user: null,
  token: null,
  initialized: false,
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
  applySession: (session) => {
    if (!session) {
      set({ user: null, token: null, initialized: true });
      return;
    }
    set({
      user: { id: session.user.id, username: readUsername(session), role: readRole(session) },
      token: session.access_token,
      initialized: true,
    });
  },
  initAuth: async () => {
    const { data } = await supabase.auth.getSession();
    get().applySession(data.session);
    supabase.auth.onAuthStateChange((_event, session) => {
      get().applySession(session);
    });
  },
  login: async (email, password) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw new Error(error.message);
  },
  logout: async () => {
    await supabase.auth.signOut();
    set({ user: null, token: null, activeProcessId: null, isMobileMenuOpen: false });
  },
}));