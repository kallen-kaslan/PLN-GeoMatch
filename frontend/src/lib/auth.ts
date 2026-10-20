import { useAppStore } from "@/store/app";

export function getToken(): string | null {
  return useAppStore.getState().token;
}
