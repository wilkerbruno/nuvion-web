// Service worker (Fase 2) — assume o papel que no app desktop era feito por
// core/managers/chrome_browser_manager.py (sessão/autenticação) e
// core/managers/pac_proxy_manager.py (aplicação de proxy). Ver plano de
// migração, seção 5, para as limitações já conhecidas: dá pra rotear
// tráfego por proxy e mascarar sinais de JS de fingerprint (content script
// da Fase 2, task #24), mas não dá pra isolar perfis/TLS por aba como o
// QtWebEngine embutido fazia — chrome.proxy é global por navegador.

import { api, clearTokens, isLoggedIn } from "./api.js";

// Credenciais do proxy ativo, guardadas só em memória (nunca em
// chrome.storage): `chrome.webRequest.onAuthRequired` roda no mesmo
// processo do service worker, então isso é suficiente enquanto ele está
// vivo. Se o service worker for descartado por inatividade, `applyActiveProxy`
// roda de novo no próximo evento (onStartup/onInstalled/mensagem do popup)
// e repopula isso antes de qualquer navegação depender dele.
let activeProxyCredentials = null;

function buildPacScript(proxy) {
  const scheme = proxy.proxy_type.toUpperCase().startsWith("SOCKS") ? "SOCKS5" : "PROXY";
  // PAC script mínimo: hosts locais vão direto, o resto passa pelo proxy
  // selecionado pelo usuário no painel/extensão. Usuário/senha não entram
  // aqui — o PAC não suporta isso; a autenticação é resolvida no listener
  // onAuthRequired abaixo.
  return `
    function FindProxyForURL(url, host) {
      if (isPlainHostName(host) || shExpMatch(host, "localhost") || shExpMatch(host, "127.0.0.1")) {
        return "DIRECT";
      }
      return "${scheme} ${proxy.host}:${proxy.port}; DIRECT";
    }
  `;
}

async function applyActiveProxy() {
  const loggedIn = await isLoggedIn();
  if (!loggedIn) {
    activeProxyCredentials = null;
    await chrome.proxy.settings.clear({ scope: "regular" });
    return;
  }

  let proxy = null;
  try {
    proxy = await api.activeProxy();
  } catch (err) {
    console.error("[Nuvion] Falha ao buscar proxy ativo:", err);
    return;
  }

  if (!proxy) {
    activeProxyCredentials = null;
    await chrome.proxy.settings.clear({ scope: "regular" });
    return;
  }

  activeProxyCredentials =
    proxy.username && proxy.password
      ? { username: proxy.username, password: proxy.password }
      : null;

  await chrome.proxy.settings.set({
    value: { mode: "pac_script", pacScript: { data: buildPacScript(proxy) } },
    scope: "regular",
  });
}

chrome.webRequest.onAuthRequired.addListener(
  (details, callback) => {
    if (details.isProxy && activeProxyCredentials) {
      callback({ authCredentials: activeProxyCredentials });
      return;
    }
    callback();
  },
  { urls: ["<all_urls>"] },
  ["asyncBlocking"]
);

async function handleMessage(message) {
  switch (message?.type) {
    case "nuvion:login": {
      await api.login(message.usernameOrEmail, message.password);
      await applyActiveProxy();
      return { ok: true };
    }
    case "nuvion:logout": {
      await clearTokens();
      activeProxyCredentials = null;
      await chrome.proxy.settings.clear({ scope: "regular" });
      return { ok: true };
    }
    case "nuvion:status": {
      const loggedIn = await isLoggedIn();
      if (!loggedIn) return { ok: true, loggedIn: false, user: null };
      try {
        const user = await api.me();
        return { ok: true, loggedIn: true, user };
      } catch {
        return { ok: true, loggedIn: false, user: null };
      }
    }
    case "nuvion:reapply-proxy": {
      await applyActiveProxy();
      return { ok: true };
    }
    default:
      return { ok: false, error: `Mensagem desconhecida: ${message?.type}` };
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  handleMessage(message)
    .then(sendResponse)
    .catch((err) => sendResponse({ ok: false, error: err.message || String(err) }));
  return true; // mantém o canal aberto para a resposta assíncrona acima
});

chrome.runtime.onStartup.addListener(() => {
  applyActiveProxy();
});

chrome.runtime.onInstalled.addListener(() => {
  applyActiveProxy();
});

// --- Fase 4: espelhar chrome.downloads no histórico do painel ---
//
// O download em si já aconteceu no navegador antes de qualquer chamada
// abaixo — isto é só espelho de status (ver plano de migração, seção 6:
// "Download real fica a cargo do navegador; extensão só espelha status").
// O mapa é em memória: se o service worker for descartado por inatividade
// no meio de um download, aquele item específico só não tem seu status
// final atualizado — não afeta o download real nem os demais itens.
const downloadIdMap = new Map(); // chrome download id -> id do registro no backend

function fileNameFromDownload(item) {
  const raw = item.filename || item.url || "arquivo";
  return raw.split(/[\\/]/).pop() || raw;
}

async function handleDownloadCreated(downloadItem) {
  if (!(await isLoggedIn())) return;
  try {
    const registered = await api.registerDownload({
      file_name: fileNameFromDownload(downloadItem),
      url: downloadItem.url,
      status: "in_progress",
    });
    downloadIdMap.set(downloadItem.id, registered.id);
  } catch (err) {
    console.error("[Nuvion] Falha ao registrar download:", err);
  }
}

async function handleDownloadChanged(delta) {
  if (!delta.state) return;
  const backendId = downloadIdMap.get(delta.id);
  if (!backendId) return;

  const current = delta.state.current;
  if (current !== "complete" && current !== "interrupted") return;

  try {
    await api.updateDownloadStatus(backendId, current === "complete" ? "completed" : "failed");
  } catch (err) {
    console.error("[Nuvion] Falha ao atualizar status de download:", err);
  } finally {
    downloadIdMap.delete(delta.id);
  }
}

chrome.downloads.onCreated.addListener(handleDownloadCreated);
chrome.downloads.onChanged.addListener(handleDownloadChanged);
