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

async function applyCookiesForTool(toolUrl, cookies, storeId) {
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
    // Sem isso o cookie vai pro cookie store "normal" (perfil comum do
    // usuário) mesmo quando a aba de destino é anônima — cada modo tem seu
    // próprio armazenamento de cookies, ver `cookieStoreIdForTab` abaixo.
    if (storeId) details.storeId = storeId;

    try {
      await chrome.cookies.set(details);
      applied += 1;
    } catch (err) {
      console.error(`[Nuvion] Falha ao aplicar cookie "${cookie.name}":`, err);
    }
  }
  return applied;
}

async function cookieStoreIdForTab(tabId) {
  try {
    const stores = await chrome.cookies.getAllCookieStores();
    const match = stores.find((store) => store.tabIds.includes(tabId));
    return match ? match.id : undefined;
  } catch (err) {
    console.error("[Nuvion] Falha ao localizar o cookie store da aba:", err);
    return undefined;
  }
}

// Abre a ferramenta numa janela ANÔNIMA (incógnito) em vez de uma janela
// comum. Isso é essencial: uma janela "normal" nova compartilha os mesmos
// cookies/sessões de todas as outras janelas do mesmo perfil do Chrome —
// então ela sempre abriria logada com a conta pessoal do usuário (se ele já
// estivesse logado naquele site em outra aba), nunca com a conta que o
// admin configurou nem "deslogada" quando nada foi configurado. Uma janela
// anônima começa sem nenhum cookie, então só fica logada com o que a
// extensão injetar de propósito (ver `applyCookiesForTool`).
//
// Isso só funciona se o usuário tiver liberado "Permitir em modo anônimo"
// pra esta extensão em chrome://extensions (o Chrome bloqueia isso por
// padrão, por privacidade — nenhuma extensão consegue ligar isso sozinha).
// Sem essa permissão, `chrome.windows.create({ incognito: true })` falha e
// caímos de volta numa janela comum (com o aviso claro pro usuário via
// `isolated: false` no retorno de `launchTool`).
//
// `type: "normal"` (não "popup"): o Chrome não permite ter abas múltiplas
// E esconder a barra de favoritos ao mesmo tempo — só "janela completa"
// (as duas coisas) ou "popup" (nenhuma das duas). Como o problema da barra
// de favoritos já foi resolvido pelos favoritos próprios da extensão (ver
// `injectBookmarkWidget` abaixo), aqui prioriza abas múltiplas normais.
async function openLaunchWindow(url) {
  try {
    const win = await chrome.windows.create({ url, type: "normal", focused: true, incognito: true });
    return { window: win, isolated: true };
  } catch (err) {
    console.error(
      "[Nuvion] Não foi possível abrir em modo anônimo — verifique se 'Permitir em modo anônimo' está ativado para a extensão em chrome://extensions. Abrindo em janela comum como alternativa:",
      err
    );
    const win = await chrome.windows.create({ url, type: "normal", focused: true });
    return { window: win, isolated: false };
  }
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

// --- Fase 5: favoritos de página PRÓPRIOS da extensão ---
//
// O Chrome não tem como isolar os favoritos NATIVOS por janela/ferramenta
// (são sempre uma lista única por perfil, mesmo em modo anônimo — não tem
// contorno pra isso, nem instalando como app). Em vez de tentar usar
// chrome.bookmarks, a extensão injeta um botão próprio na página; ele
// manda o que o usuário quiser salvar pro backend (`POST /tool-bookmarks`),
// numa lista à parte, ligada à conta do usuário — não ao navegador.
//
// `activeLaunchTabs` guarda, por aba, qual ferramenta está aberta ali —
// usado só pra saber quando reinjetar o botão (a ferramenta pode navegar
// pra outras páginas com reload completo, o que apaga o botão anterior).
const activeLaunchTabs = new Map(); // tabId -> { toolId, toolName }

// Injetada via chrome.scripting.executeScript — precisa ser autocontida
// (sem closures sobre variáveis do service worker), já que roda isolada no
// contexto da aba de destino. Roda no mundo "ISOLATED" (padrão), então tem
// acesso a chrome.runtime.sendMessage normalmente.
function injectBookmarkWidget({ toolId, toolName }) {
  const EXISTING_ID = "nuvion-bookmark-widget";
  const existing = document.getElementById(EXISTING_ID);
  if (existing) existing.remove(); // reinjeção após navegação — evita duplicar

  const button = document.createElement("button");
  button.id = EXISTING_ID;
  button.type = "button";
  button.textContent = "★ Favoritar esta página";
  button.style.cssText = [
    "position:fixed",
    "bottom:16px",
    "right:16px",
    "z-index:2147483647",
    "padding:9px 14px",
    "background:#2fbfa6",
    "color:#06231e",
    "border:none",
    "border-radius:20px",
    "font:600 12px -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif",
    "cursor:pointer",
    "box-shadow:0 2px 10px rgba(0,0,0,.35)",
  ].join(";");

  button.addEventListener("click", () => {
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Salvando...";
    chrome.runtime.sendMessage(
      {
        type: "nuvion:save-bookmark",
        toolId,
        url: window.location.href,
        title: document.title || toolName,
      },
      (response) => {
        button.disabled = false;
        button.textContent = response && response.ok ? "✓ Favoritado" : "Falha ao salvar";
        setTimeout(() => {
          button.textContent = original;
        }, 2000);
      }
    );
  });

  document.body.appendChild(button);
}

async function injectBookmarkWidgetIntoTab(tabId, payload) {
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      func: injectBookmarkWidget,
      args: [payload],
    });
  } catch (err) {
    // Comum em páginas onde a extensão não pode injetar (chrome://,
    // Chrome Web Store, etc.) — não é um erro que trave o resto do fluxo.
    console.debug("[Nuvion] Não foi possível injetar o botão de favoritos nesta página:", err);
  }
}

// Reinjeta o botão sempre que a aba rastreada termina de carregar uma nova
// página (navegação com reload completo apaga o DOM anterior, inclusive o
// botão). Navegação só de rota (SPA, sem reload) preserva o botão sozinha.
chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.status !== "complete") return;
  const tracked = activeLaunchTabs.get(tabId);
  if (tracked) injectBookmarkWidgetIntoTab(tabId, tracked);
});

chrome.tabs.onRemoved.addListener((tabId) => {
  activeLaunchTabs.delete(tabId);
});

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

async function launchTool(toolId, { url: overrideUrl } = {}) {
  const launch = await api.launchTool(toolId);
  const targetUrl = overrideUrl || launch.url; // overrideUrl = abrindo um favorito salvo, não a URL padrão da ferramenta

  if (launch.proxy) {
    await registerToolProxy(new URL(targetUrl).hostname, launch.proxy);
  }

  // Abre em branco primeiro (não já na URL de destino): precisamos do
  // storeId de cookies dessa aba/janela ANTES de navegar, senão a página
  // carrega antes do cookie de sessão existir e mostra a tela de login
  // mesmo com tudo certo (o usuário só veria funcionar depois de recarregar
  // manualmente). Só navega pra URL de verdade depois do cookie aplicado.
  const { window: win, isolated } = await openLaunchWindow("about:blank");
  let tab = win.tabs && win.tabs[0] ? win.tabs[0] : null;
  if (!tab) {
    const tabs = await chrome.tabs.query({ windowId: win.id });
    tab = tabs[0] || null;
  }

  let loginMethodUsed = "manual";
  if (launch.cookies && launch.cookies.length > 0) {
    const storeId = tab?.id ? await cookieStoreIdForTab(tab.id) : undefined;
    const applied = await applyCookiesForTool(targetUrl, launch.cookies, storeId);
    if (applied > 0) loginMethodUsed = "cookies";
  }

  if (tab?.id) {
    activeLaunchTabs.set(tab.id, { toolId, toolName: launch.name });
    await chrome.tabs.update(tab.id, { url: targetUrl });
  }

  if (tab?.id) {
    const loaded = await waitForTabComplete(tab.id);
    if (loaded) {
      await injectBookmarkWidgetIntoTab(tab.id, { toolId, toolName: launch.name });

      if (loginMethodUsed !== "cookies" && launch.credentials) {
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
  }

  return {
    ok: true,
    opened: true,
    loginMethod: loginMethodUsed,
    proxyApplied: Boolean(launch.proxy),
    isolated,
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
      return launchTool(message.toolId, { url: message.url });
    }
    case "nuvion:save-bookmark": {
      const bookmark = await api.saveToolBookmark(message.toolId, message.url, message.title);
      return { ok: true, bookmark };
    }
    case "nuvion:list-bookmarks": {
      const bookmarks = await api.listToolBookmarks();
      return { ok: true, bookmarks };
    }
    case "nuvion:delete-bookmark": {
      await api.deleteToolBookmark(message.bookmarkId);
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
