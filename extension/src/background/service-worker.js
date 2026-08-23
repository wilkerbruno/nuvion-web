// Service worker (Fase 2, estendido na Fase 5) — assume o papel que no app
// desktop era feito por core/managers/chrome_browser_manager.py
// (sessão/autenticação) e core/managers/pac_proxy_manager.py (aplicação de
// proxy). Ver plano de migração, seção 5, para as limitações já
// conhecidas: dá pra rotear tráfego por proxy e mascarar sinais de JS de
// fingerprint (content script da Fase 2, task #24), mas não dá pra isolar
// perfis/TLS por aba como o QtWebEngine embutido fazia — chrome.proxy é
// global por navegador, nunca por aba/janela.
//
// Fase 5 (task #79) empilha em cima disso o roteamento POR DOMÍNIO DE
// FERRAMENTA: cada ferramenta de IA pode ter um proxy próprio atribuído
// pelo admin (`AITool.proxy_id`, ver GET /ai-tools/{id}/launch). Como não
// existe proxy "por janela" no Chrome, a saída combinada com o usuário foi
// um único PAC script que decide o proxy PELO HOSTNAME de destino: os
// domínios das ferramentas já abertas nesta sessão do navegador usam o
// proxy atribuído a elas, e todo o resto (inclusive navegação normal) cai
// no proxy pessoal do usuário (ou DIRECT, se ele não tiver um selecionado).

import { api, clearTokens, isLoggedIn } from "./api.js";

// Estado do roteamento de proxy, tudo só em memória (nunca em
// chrome.storage — são credenciais): se o service worker for descartado
// por inatividade, esse estado zera e é reconstruído aos poucos —
// `applyActiveProxy()` roda de novo no próximo evento (onStartup/
// onInstalled/mensagem do popup) e repõe o proxy pessoal; os proxies por
// ferramenta voltam a ser registrados na próxima vez que o usuário abrir
// aquela ferramenta pela extensão. Nunca deixa a navegação sem proxy
// nenhum por mais tempo que isso.
let defaultProxy = null; // proxy pessoal ativo do usuário (GET /proxies/active)
const toolProxiesByDomain = new Map(); // hostname da ferramenta -> { host, port, proxy_type }
const proxyAuthByHostPort = new Map(); // "host:port" -> { username, password }

function registerProxyAuth(proxy) {
  if (proxy?.username && proxy?.password) {
    proxyAuthByHostPort.set(`${proxy.host}:${proxy.port}`, {
      username: proxy.username,
      password: proxy.password,
    });
  }
}

function pacClauseForProxy(proxy) {
  const scheme = proxy.proxy_type.toUpperCase().startsWith("SOCKS") ? "SOCKS5" : "PROXY";
  return `${scheme} ${proxy.host}:${proxy.port}; DIRECT`;
}

function buildCombinedPacScript() {
  // Uma cláusula por ferramenta com proxy atribuído, checando o host exato
  // e subdomínios; hosts locais sempre vão direto; qualquer outro domínio
  // (navegação normal + ferramentas sem proxy configurado) cai no proxy
  // pessoal do usuário, se houver.
  const domainRules = Array.from(toolProxiesByDomain.entries())
    .map(
      ([domain, proxy]) =>
        `if (host === "${domain}" || dnsDomainIs(host, ".${domain}")) { return "${pacClauseForProxy(proxy)}"; }`
    )
    .join("\n      ");

  const fallbackClause = defaultProxy ? `return "${pacClauseForProxy(defaultProxy)}";` : `return "DIRECT";`;

  return `
    function FindProxyForURL(url, host) {
      if (isPlainHostName(host) || shExpMatch(host, "localhost") || shExpMatch(host, "127.0.0.1")) {
        return "DIRECT";
      }
      ${domainRules}
      ${fallbackClause}
    }
  `;
}

async function applyCombinedProxySettings() {
  if (!defaultProxy && toolProxiesByDomain.size === 0) {
    await chrome.proxy.settings.clear({ scope: "regular" });
    return;
  }
  await chrome.proxy.settings.set({
    value: { mode: "pac_script", pacScript: { data: buildCombinedPacScript() } },
    scope: "regular",
  });
}

async function applyActiveProxy() {
  const loggedIn = await isLoggedIn();
  if (!loggedIn) {
    defaultProxy = null;
    toolProxiesByDomain.clear();
    proxyAuthByHostPort.clear();
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

  defaultProxy = proxy || null;
  if (defaultProxy) registerProxyAuth(defaultProxy);
  await applyCombinedProxySettings();
}

// Atribui o proxy de uma ferramenta específica ao domínio dela — chamado
// ao abrir a ferramenta (ver `launchTool` abaixo). Fica registrado
// enquanto o service worker estiver vivo, então reaberturas da mesma
// ferramenta na mesma sessão do navegador não precisam reconsultar nada.
async function registerToolProxy(domain, proxy) {
  toolProxiesByDomain.set(domain, proxy);
  registerProxyAuth(proxy);
  await applyCombinedProxySettings();
}

chrome.webRequest.onAuthRequired.addListener(
  (details, callback) => {
    if (details.isProxy && details.challenger) {
      const creds = proxyAuthByHostPort.get(`${details.challenger.host}:${details.challenger.port}`);
      if (creds) {
        callback({ authCredentials: creds });
        return;
      }
    }
    callback();
  },
  { urls: ["<all_urls>"] },
  ["asyncBlocking"]
);

// --- Fase 5: abrir ferramenta de IA já logada + já roteada pelo proxy ---
//
// Combinação acordada com o usuário: cookie de sessão é o método
// principal de login automático; preencher usuário/senha (autofill, sem
// clicar em enviar) só entra como reforço quando a ferramenta não tem
// cookie de sessão configurado — nunca os dois ao mesmo tempo, pra não
// sobrescrever um login que já chegou autenticado via cookie.

function sameSiteForChrome(value) {
  const v = (value || "").toLowerCase();
  if (v === "no_restriction" || v === "none") return "no_restriction";
  if (v === "strict") return "strict";
  if (v === "lax") return "lax";
  return "unspecified";
}

async function applyCookiesForTool(toolUrl, cookies) {
  let applied = 0;
  const fallbackDomain = new URL(toolUrl).hostname;

  for (const cookie of cookies) {
    if (!cookie?.name || cookie.value === undefined) continue;
    const domain = (cookie.domain || fallbackDomain).replace(/^\./, "");
    const details = {
      url: `https://${domain}${cookie.path || "/"}`,
      name: cookie.name,
      value: cookie.value,
      path: cookie.path || "/",
      secure: cookie.secure !== false,
      httpOnly: Boolean(cookie.httpOnly),
      sameSite: sameSiteForChrome(cookie.sameSite),
    };
    if (cookie.domain) details.domain = cookie.domain;
    if (typeof cookie.expirationDate === "number") details.expirationDate = cookie.expirationDate;

    try {
      await chrome.cookies.set(details);
      applied += 1;
    } catch (err) {
      console.error(`[Nuvion] Falha ao aplicar cookie "${cookie.name}":`, err);
    }
  }
  return applied;
}

// Injetada via chrome.scripting.executeScript — precisa ser autocontida
// (sem closures sobre variáveis do service worker), já que roda isolada no
// contexto da aba de destino.
function autofillLoginForm({ usernameSelector, passwordSelector, username, password }) {
  function setNativeValue(el, value) {
    const proto = Object.getPrototypeOf(el);
    const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
    if (setter) setter.call(el, value);
    else el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }

  const userEl = usernameSelector ? document.querySelector(usernameSelector) : null;
  const passEl = passwordSelector ? document.querySelector(passwordSelector) : null;
  if (userEl) setNativeValue(userEl, username);
  if (passEl) setNativeValue(passEl, password);

  // Só preenche — não clica em enviar. Quem confirma o login é o usuário,
  // vendo os campos já preenchidos (evita gatilhos inesperados em sites de
  // terceiros: 2FA, captcha, "dispositivo novo", etc.).
  return { filled: Boolean(userEl && passEl) };
}

function waitForTabComplete(tabId, timeoutMs = 15000) {
  return new Promise((resolve) => {
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      chrome.tabs.onUpdated.removeListener(listener);
      resolve(false);
    }, timeoutMs);

    function listener(id, changeInfo) {
      if (id !== tabId || changeInfo.status !== "complete" || settled) return;
      settled = true;
      clearTimeout(timer);
      chrome.tabs.onUpdated.removeListener(listener);
      resolve(true);
    }
    chrome.tabs.onUpdated.addListener(listener);
  });
}

async function launchTool(toolId) {
  const launch = await api.launchTool(toolId);

  if (launch.proxy) {
    await registerToolProxy(new URL(launch.url).hostname, launch.proxy);
  }

  let loginMethodUsed = "manual";
  if (launch.cookies && launch.cookies.length > 0) {
    const applied = await applyCookiesForTool(launch.url, launch.cookies);
    if (applied > 0) loginMethodUsed = "cookies";
  }

  const win = await chrome.windows.create({ url: launch.url, type: "normal", focused: true });
  let tab = win.tabs && win.tabs[0] ? win.tabs[0] : null;
  if (!tab) {
    const tabs = await chrome.tabs.query({ windowId: win.id });
    tab = tabs[0] || null;
  }

  if (loginMethodUsed !== "cookies" && launch.credentials && tab?.id) {
    const loaded = await waitForTabComplete(tab.id);
    if (loaded) {
      try {
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: autofillLoginForm,
          args: [
            {
              usernameSelector: launch.credentials.username_selector,
              passwordSelector: launch.credentials.password_selector,
              username: launch.credentials.username,
              password: launch.credentials.password,
            },
          ],
        });
        loginMethodUsed = "credentials";
      } catch (err) {
        console.error("[Nuvion] Falha ao preencher formulário de login:", err);
      }
    }
  }

  return {
    ok: true,
    opened: true,
    loginMethod: loginMethodUsed,
    proxyApplied: Boolean(launch.proxy),
  };
}

async function handleMessage(message) {
  switch (message?.type) {
    case "nuvion:login": {
      await api.login(message.usernameOrEmail, message.password);
      await applyActiveProxy();
      return { ok: true };
    }
    case "nuvion:logout": {
      await clearTokens();
      defaultProxy = null;
      toolProxiesByDomain.clear();
      proxyAuthByHostPort.clear();
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
    case "nuvion:launch-tool": {
      return launchTool(message.toolId);
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
