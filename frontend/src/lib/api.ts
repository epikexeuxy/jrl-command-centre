/** Minimal API client for the platform shell. The full typed client lands with the Phase 1 UI. */
import axios from "axios";

export const api = axios.create({ baseURL: "/api/v1" });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("jrl.access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  database: string;
}
