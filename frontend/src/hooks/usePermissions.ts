import { useAppStore } from "@/store/app";

export function usePermissions() {
  const role = useAppStore((state) => state.user?.role);
  return {
    canWrite: role === "admin" || role === "analis",
    canDelete: role === "admin",
  };
}
