import axios, { AxiosError } from "axios";
import type { InternalAxiosRequestConfig } from "axios";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

let getToken: (() => string | null) | null = null;

export function setTokenGetter(fn: () => string | null) {
  getToken = fn;
}

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (getToken) {
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err: AxiosError<{ message?: string; detail?: string }>) => {
    const status = err.response?.status;
    const data = err.response?.data;
    let message = data?.message ?? data?.detail ?? err.message ?? "Terjadi kesalahan";
    if (status === 502) {
      message = "Koneksi ke backend terputus (502 Bad Gateway). Pastikan server backend FastAPI berjalan di http://localhost:8000.";
    }
    return Promise.reject({ status, message, data });
  },
);

export type ApiError = { status?: number; message: string; data?: unknown };
