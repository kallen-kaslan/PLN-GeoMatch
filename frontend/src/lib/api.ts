import axios, { AxiosError } from "axios";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
    "X-Requested-With": "PLN-GeoMatch",
  },
});

api.interceptors.request.use((config) => {
  if (!["get", "head", "options"].includes(config.method ?? "get")) {
    const cookies = document.cookie.split(/;\s*/);
    const cookie = cookies.find((value) => value.startsWith("__Host-geomatch_csrf=")) ?? cookies.find((value) => value.startsWith("geomatch_csrf="));
    if (cookie) config.headers["X-CSRF-Token"] = decodeURIComponent(cookie.slice(cookie.indexOf("=") + 1));
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err: AxiosError<{ message?: string; detail?: string | { msg: string }[] }>) => {
    const status = err.response?.status;
    const data = err.response?.data;
    const detail = data?.detail;
    let message = data?.message ?? (typeof detail === "string" ? detail : detail?.map((item) => item.msg).join(". ")) ?? err.message ?? "Terjadi kesalahan";
    if (status === 401 && err.config?.url !== "/auth/login" && err.config?.url !== "/auth/me") {
      window.dispatchEvent(new Event("geomatch:unauthorized"));
    }
    if (status === 502) {
      message = "Koneksi ke backend terputus (502 Bad Gateway). Pastikan server backend FastAPI berjalan di http://localhost:8000.";
    }
    return Promise.reject({ status, message, data });
  },
);

export type ApiError = { status?: number; message: string; data?: unknown };
