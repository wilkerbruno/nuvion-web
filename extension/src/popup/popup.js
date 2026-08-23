// Popup (Fase 2, MVP) — login, status da conta e do proxy ativo, logout.
// Equivalente web de core/login_window.py + a barra de status do app
// desktop, só que como um popup de extensão em vez de uma janela Qt.
//
// Login/logout/status passam por mensagem para o service worker
// (../background/service-worker.js) — é ele quem mantém a fonte da
// verdade do token e do proxy aplicado (chrome.proxy.settings). Leituras
// simples (proxy ativo) usam o cliente da API diretamente, já que o popup
// tem os mesmos acessos de extensão que o background.
import { api, getFrontendUrl } from "../background/api.js";

const els = {};

function $(id) {
  return document.getElementById(id);
}

function sendMessage(message) {
  return chrome.runtime.sendMessage(message);
}

function showView(view) {
  els.loginView.hidden = view !== "login";
  els.statusView.hidden = view !== "status";
}

async function renderStatus() {
  els.statusError.hidden = true;

  const status = await sendMessage({ type: "nuvion:status" });
  if (!status || !status.ok || !status.loggedIn) {
    showView("login");
    return;
  }

  const user = status.user;
  els.userLine.textContent = `${user.name} (@${user.username})`;
  els.accountLine.textContent = `${user.account_type} · ${user.status}`;

  els.proxyLine.textContent = "Carregando proxy...";
  try {
    const proxy = await api.activeProxy();
    els.proxyLine.textContent = proxy
      ? `Proxy ativo: ${proxy.name} (${proxy.host}:${proxy.port})`
      : "Nenhum proxy selecionado — escolha um no painel.";
  } catch (err) {
    els.proxyLine.textContent = "Não foi possível carregar o proxy ativo.";
    console.debug("[Nuvion] activeProxy falhou:", err);
  }

  els.notificationsLine.textContent = "Carregando notificações...";
  try {
    const { unread_count: unreadCount } = await api.unreadNotificationCount();
    els.notificationsLine.textContent =
      unreadCount > 0 ? `🔔 ${unreadCount} notificação(ões) não lida(s)` : "Sem notificações novas";
  } catch (err) {
    els.notificationsLine.textContent = "Não foi possível carregar notificações.";
    console.debug("[Nuvion] unreadNotificationCount falhou:", err);
  }

  await renderTools();

  showView("status");
}

// Fase 5: lista de ferramentas de IA com um botão "Abrir" por linha — abre
// já roteada pelo proxy atribuído pelo admin e já logada (cookie/senha),
// tudo tratado pelo service worker via mensagem `nuvion:launch-tool`.
async function renderTools() {
  els.toolsList.textContent = "Carregando...";
  try {
    const tools = await api.aiTools();
    if (!tools || tools.length === 0) {
      els.toolsList.textContent = "Nenhuma ferramenta cadastrada ainda.";
      return;
    }
    els.toolsList.innerHTML = "";
    tools.forEach((tool) => {
      const row = document.createElement("div");
      row.className = "tool-row";

      const name = document.createElement("div");
      name.className = "tool-name";
      name.textContent = tool.name;
      name.title = tool.name;

      const button = document.createElement("button");
      button.type = "button";
      button.className = "tool-open-btn";
      button.textContent = "Abrir";
      button.addEventListener("click", () => handleOpenTool(tool, button));

      row.appendChild(name);
      row.appendChild(button);
      els.toolsList.appendChild(row);
    });
  } catch (err) {
    els.toolsList.textContent = "Não foi possível carregar as ferramentas.";
    console.debug("[Nuvion] aiTools falhou:", err);
  }
}

async function handleOpenTool(tool, button) {
  const originalLabel = button.textContent;
  button.disabled = true;
  button.textContent = "Abrindo...";
  els.statusError.hidden = true;

  try {
    const response = await sendMessage({ type: "nuvion:launch-tool", toolId: tool.id });
    if (!response || !response.ok) {
      throw new Error((response && response.error) || "Falha ao abrir ferramenta");
    }
    if (response.isolated === false) {
      // A extensão não conseguiu abrir em modo anônimo (o Chrome exige que
      // o usuário libere isso manualmente) — a ferramenta abriu, mas numa
      // janela comum, que compartilha login com as outras abas do usuário.
      els.statusError.textContent =
        'Ferramenta aberta, mas sem isolamento de conta: ative "Permitir em modo anônimo" para a extensão Nuvion Web em chrome://extensions para abrir sempre com a conta certa.';
      els.statusError.hidden = false;
    }
  } catch (err) {
    els.statusError.textContent = `Falha ao abrir "${tool.name}": ${err.message || err}`;
    els.statusError.hidden = false;
    console.error("[Nuvion] Falha ao abrir ferramenta:", err);
  } finally {
    button.disabled = false;
    button.textContent = originalLabel;
  }
}

async function handleLogin(event) {
  event.preventDefault();
  els.loginError.hidden = true;
  els.loginButton.disabled = true;
  els.loginButton.textContent = "Entrando...";

  try {
    const response = await sendMessage({
      type: "nuvion:login",
      usernameOrEmail: els.usernameInput.value.trim(),
      password: els.passwordInput.value,
    });
    if (!response || !response.ok) {
      throw new Error((response && response.error) || "Falha ao entrar");
    }
    els.passwordInput.value = "";
    await renderStatus();
  } catch (err) {
    els.loginError.textContent = err.message || String(err);
    els.loginError.hidden = false;
  } finally {
    els.loginButton.disabled = false;
    els.loginButton.textContent = "Entrar";
  }
}

async function handleLogout() {
  await sendMessage({ type: "nuvion:logout" });
  await renderStatus();
}

async function handleReapplyProxy() {
  els.reapplyButton.disabled = true;
  els.reapplyButton.textContent = "Aplicando...";
  await sendMessage({ type: "nuvion:reapply-proxy" });
  await renderStatus();
  els.reapplyButton.disabled = false;
  els.reapplyButton.textContent = "Reaplicar proxy";
}

async function openDashboard() {
  const frontendUrl = await getFrontendUrl();
  chrome.tabs.create({ url: frontendUrl });
}

function openSettings() {
  chrome.runtime.openOptionsPage();
}

document.addEventListener("DOMContentLoaded", () => {
  els.loginView = $("login-view");
  els.statusView = $("status-view");
  els.loginForm = $("login-form");
  els.usernameInput = $("username");
  els.passwordInput = $("password");
  els.loginButton = $("login-button");
  els.loginError = $("login-error");
  els.statusError = $("status-error");
  els.userLine = $("user-line");
  els.accountLine = $("account-line");
  els.proxyLine = $("proxy-line");
  els.notificationsLine = $("notifications-line");
  els.toolsList = $("tools-list");
  els.logoutButton = $("logout-button");
  els.reapplyButton = $("reapply-button");
  els.settingsButton = $("settings-button");

  els.loginForm.addEventListener("submit", handleLogin);
  els.logoutButton.addEventListener("click", handleLogout);
  els.reapplyButton.addEventListener("click", handleReapplyProxy);
  els.settingsButton.addEventListener("click", openSettings);
  document
    .querySelectorAll("[data-open-dashboard]")
    .forEach((el) => el.addEventListener("click", openDashboard));

  renderStatus();
});
