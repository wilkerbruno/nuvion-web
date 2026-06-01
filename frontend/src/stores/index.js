// frontend/src/stores/index.js
import { create } from "zustand";
import { persist } from "zustand/middleware";
import api from "../lib/api";

// ── Auth Store ────────────────────────────────────────────────────────────────
export const useAuthStore = create(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,

      setTokens: (access, refresh) =>
        set({ accessToken: access, refreshToken: refresh }),

      setUser: (user) => set({ user }),

      login: async (username, password) => {
        const { data } = await api.post("/auth/login", { username, password });
        set({
          user: data.user,
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
        });
        return data.user;
      },

      register: async (payload) => {
        await api.post("/auth/register", payload);
      },

      logout: () => set({ user: null, accessToken: null, refreshToken: null }),

      refreshAccessToken: async () => {
        const { refreshToken } = get();
        if (!refreshToken) throw new Error("Sem refresh token");
        const { data } = await api.post("/auth/refresh", {
          refresh_token: refreshToken,
        });
        set({
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
          user: data.user,
        });
        return data.access_token;
      },

      isAdmin: () => get().user?.account_type === "Admin",
      isLoggedIn: () => !!get().user,
    }),
    { name: "nuvion-auth", partialize: (s) => ({ user: s.user, accessToken: s.accessToken, refreshToken: s.refreshToken }) }
  )
);

// ── Tools Store ───────────────────────────────────────────────────────────────
export const useToolsStore = create((set, get) => ({
  tools: [],
  loading: false,
  category: "todas",
  search: "",
  viewMode: "cards",

  setCategory: (c) => set({ category: c }),
  setSearch: (s) => set({ search: s }),
  setViewMode: (m) => set({ viewMode: m }),

  fetchTools: async () => {
    set({ loading: true });
    try {
      const { category } = get();
      const params = {};
      if (category && category !== "todas") params.category = category;
      const { data } = await api.get("/tools", { params });
      set({ tools: data });
    } finally {
      set({ loading: false });
    }
  },

  toggleFavorite: async (toolId) => {
    await api.post(`/favorites/${toolId}`);
    set((s) => ({
      tools: s.tools.map((t) =>
        t.id === toolId ? { ...t, is_favorite: !t.is_favorite } : t
      ),
    }));
  },

  deleteTool: async (toolId) => {
    await api.delete(`/tools/${toolId}`);
    set((s) => ({ tools: s.tools.filter((t) => t.id !== toolId) }));
  },

  openTool: async (toolId) => {
    const { data } = await api.post(`/tools/${toolId}/open`);
    return data.job_id;
  },

  filteredTools: () => {
    const { tools, category, search } = get();
    let filtered = tools;

    if (category === "favoritos") filtered = filtered.filter((t) => t.is_favorite);
    else if (category && category !== "todas")
      filtered = filtered.filter((t) => t.category === category);

    if (search) {
      const q = search.toLowerCase();
      filtered = filtered.filter(
        (t) =>
          t.name.toLowerCase().includes(q) ||
          t.url.toLowerCase().includes(q) ||
          (t.tags || []).some((tag) => tag.toLowerCase().includes(q))
      );
    }
    return filtered;
  },
}));

// ── Notifications Store ───────────────────────────────────────────────────────
export const useNotifStore = create((set) => ({
  notifications: [],
  unreadCount: 0,

  fetchNotifications: async () => {
    const { data } = await api.get("/notifications");
    set({ notifications: data });
  },

  fetchUnreadCount: async () => {
    const { data } = await api.get("/notifications/unread-count");
    set({ unreadCount: data.count });
  },

  markRead: async (id) => {
    await api.post(`/notifications/${id}/read`);
    set((s) => ({
      notifications: s.notifications.map((n) =>
        n.id === id ? { ...n, is_read: true } : n
      ),
      unreadCount: Math.max(0, s.unreadCount - 1),
    }));
  },

  markAllRead: async () => {
    await api.post("/notifications/read-all");
    set((s) => ({
      notifications: s.notifications.map((n) => ({ ...n, is_read: true })),
      unreadCount: 0,
    }));
  },
}));
