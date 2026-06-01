// frontend/src/lib/api.js
import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
  timeout: 30000,
});

// Injeta token em toda requisição
api.interceptors.request.use((config) => {
  const raw = localStorage.getItem("nuvion-auth");
  if (raw) {
    const { state } = JSON.parse(raw);
    if (state?.accessToken) {
      config.headers.Authorization = `Bearer ${state.accessToken}`;
    }
  }
  return config;
});

// Refresh automático em 401
let refreshing = null;

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;

      if (!refreshing) {
        refreshing = (async () => {
          try {
            const { useAuthStore } = await import("../stores");
            const newToken = await useAuthStore.getState().refreshAccessToken();
            return newToken;
          } catch {
            const { useAuthStore } = await import("../stores");
            useAuthStore.getState().logout();
            window.location.href = "/login";
            return null;
          } finally {
            refreshing = null;
          }
        })();
      }

      const newToken = await refreshing;
      if (newToken) {
        original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      }
    }
    return Promise.reject(error);
  }
);

export default api;
