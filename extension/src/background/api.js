// Cliente HTTP para o backend Nuvion Web, usado pelo service worker e pelo
// popup. Equivalente de frontend/lib/api.ts, mas com o token guardado em
// `chrome.storage.local` — service workers não têm acesso a `localStorage`
// (nem a `window`).
//
// Módulo ES (o manifest declara "type": "module" no background), então dá
// pra usar import/export normalmente.
//
// URL do backend e do painel: guardadas em chrome.storage.local (não são
// mais uma constante fixa no código) — ver src/options/. Isso existe pra
// não precisar editar código/recarregar a extensão toda vez que ela aponta
// pra um ambiente diferente (localhost em desenvolvimento, o domínio real
// depois que o backend for publicado no EasyPanel).

const DEFAULT_API_BASE_URL = "http://localhost:8000";
const DEFAULT_FRONTEND_URL = "http://localhost:3000";

const STORAGE_KEYS = {
  apiBaseUrl: "nuvion_api_base_url",
  frontendUrl: "nuvion_frontend_url",
  accessToken: "nuvion_access_token",
  refreshToken: "nuvion_refresh_token",
};

export async function getApiBaseUrl() {
  const stored = await chrome.storage.local.get(STORAGE_KEYS.apiBaseUrl);
  return stored[STORAGE_KEYS.apiBaseUrl] || DEFAULT_API_BASE_URL;
}

export async function setApiBaseUrl(url) {
  await chrome.storage.local.set({ [STORAGE_KEYS.apiBaseUrl]: url });
}

export async function getFrontendUrl() {
  const stored = await chrome.storage.local.get(STORAGE_KEYS.frontendUrl);
  return stored[STORAGE_KEYS.frontendUrl] || DEFAULT_FRONTEND_URL;
}

export async function setFrontendUrl(url) {
  await chrome.storage.local.set({ [STORAGE_KEYS.frontendUrl]: url });
}

export { DEFAULT_API_BASE_URL, DEFAULT_FRONTEND_URL };

export async function getTokens() {
  const stored = await chrome.storage.local.get([
    STORAGE_KEYS.accessToken,
    STORAGE_KEYS.refreshToken,
  ]);
  return {
    accessToken: stored[STORAGE_KEYS.accessToken] || null,
    refreshToken: stored[STORAGE_KEYS.refreshToken] || null,
  };
}

export async function saveTokens({ access_token, refresh_token }) {
  await chrome.storage.local.set({
    [STORAGE_KEYS.accessToken]: access_token,
    [STORAGE_KEYS.refreshToken]: refresh_token,
  });
}

export async function clearTokens() {
  await chrome.storage.local.remove([STORAGE_KEYS.accessToken, STORAGE_KEYS.refreshToken]);
}

export async function isLoggedIn() {
  const { accessToken } = await getTokens();
  return Boolean(accessToken);
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function request(path, { method = "GET", body, auth = true, retry = true } = {}) {
  const baseUrl = await getApiBaseUrl();
  const headers = { "Content-Type": "application/json" };

  if (auth) {
    const { accessToken } = await getTokens();
    if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  }

  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (response.status === 401 && auth && retry) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      return request(path, { method, body, auth, retry: false });
    }
    await clearTokens();
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const errBody = await response.json();
      if (errBody && errBody.detail) detail = errBody.detail;
    } catch {
      // corpo de erro não era JSON — mantém o statusText
    }
    throw new ApiError(typeof detail === "string" ? detail : JSON.stringify(detail), response.status);
  }

  if (response.status === 204) return null;
  return response.json();
}

async function tryRefreshToken() {
  const { refreshToken } = await getTokens();
  if (!refreshToken) return false;

  try {
    const baseUrl = await getApiBaseUrl();
    const response = await fetch(`${baseUrl}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!response.ok) return false;
    const data = await response.json();
    await chrome.storage.local.set({ [STORAGE_KEYS.accessToken]: data.access_token });
    return true;
  } catch {
    return false;
  }
}

export const api = {
  async login(usernameOrEmail, password) {
    const tokens = await request("/auth/login", {
      method: "POST",
      auth: false,
      body: { username_or_email: usernameOrEmail, password },
    });
    await saveTokens(tokens);
    return tokens;
  },

  async me() {
    return request("/auth/me");
  },

  async dashboard() {
    return request("/dashboard/me");
  },

  async proxies() {
    return request("/proxies");
  },

  async activeProxy() {
    try {
      return await request("/proxies/active");
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) return null;
      throw err;
    }
  },

  async selectProxy(proxyId) {
    return request(`/proxies/${proxyId}/select`, { method: "POST" });
  },

  async browserSettings() {
    return request("/browser-settings/me");
  },

  // --- Fase 5: abrir ferramenta de IA já logada + roteada por proxy ---
  async aiTools() {
    return request("/ai-tools");
  },

  async launchTool(toolId) {
    return request(`/ai-tools/${toolId}/launch`);
  },

  // --- Fase 5: favoritos de página por ferramenta (próprios da extensão,
  // não os favoritos nativos do Chrome — ver app/models/tool_bookmark.py) ---
  async listToolBookmarks(aiToolId) {
    const query = aiToolId ? `?ai_tool_id=${encodeURIComponent(aiToolId)}` : "";
    return request(`/tool-bookmarks${query}`);
  },

  async saveToolBookmark(aiToolId, url, title) {
    return request("/tool-bookmarks", {
      method: "POST",
      body: { ai_tool_id: aiToolId, url, title },
    });
  },

  async deleteToolBookmark(bookmarkId) {
    return request(`/tool-bookmarks/${bookmarkId}`, { method: "DELETE" });
  },

  // --- Fase 4: notificações + downloads ---
  async unreadNotificationCount() {
    return request("/notifications/me/unread-count");
  },

  async registerDownload({ file_name, file_path, url, status }) {
    return request("/downloads", { method: "POST", body: { file_name, file_path, url, status } });
  },

  async updateDownloadStatus(downloadId, status) {
    return request(`/downloads/${downloadId}`, { method: "PATCH", body: { status } });
  },
};
