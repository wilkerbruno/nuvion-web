// Tela de configuração da extensão — troca a URL do backend/painel sem
// precisar editar código nem recarregar a extensão. Guardado em
// chrome.storage.local via src/background/api.js (mesmo módulo usado pelo
// service worker e pelo popup, então uma alteração aqui já vale pra eles
// na próxima chamada).
import {
  DEFAULT_API_BASE_URL,
  DEFAULT_FRONTEND_URL,
  getApiBaseUrl,
  getFrontendUrl,
  setApiBaseUrl,
  setFrontendUrl,
} from "../background/api.js";

const els = {};

function $(id) {
  return document.getElementById(id);
}

function showStatus(message, kind) {
  els.status.textContent = message;
  els.status.className = `status ${kind}`;
  els.status.hidden = false;
}

function normalizeUrl(value) {
  // Remove barra final (pra não gerar "http://host//health" etc. quando
  // concatenar caminhos em src/background/api.js).
  return value.trim().replace(/\/+$/, "");
}

async function loadCurrentValues() {
  els.apiUrl.value = await getApiBaseUrl();
  els.frontendUrl.value = await getFrontendUrl();
}

async function handleSave(event) {
  event.preventDefault();
  const apiUrl = normalizeUrl(els.apiUrl.value);
  const frontendUrl = normalizeUrl(els.frontendUrl.value);

  if (!apiUrl || !frontendUrl) {
    showStatus("Preencha as duas URLs.", "error");
    return;
  }

  await setApiBaseUrl(apiUrl);
  await setFrontendUrl(frontendUrl);
  els.apiUrl.value = apiUrl;
  els.frontendUrl.value = frontendUrl;
  showStatus("Salvo. As próximas chamadas da extensão já usam essas URLs.", "ok");
}

async function handleTestConnection() {
  const apiUrl = normalizeUrl(els.apiUrl.value);
  if (!apiUrl) {
    showStatus("Preencha a URL do backend antes de testar.", "error");
    return;
  }

  els.testButton.disabled = true;
  els.testButton.textContent = "Testando...";
  try {
    const response = await fetch(`${apiUrl}/health`, { method: "GET" });
    if (response.ok) {
      showStatus(`✓ Backend respondeu em ${apiUrl}/health (status ${response.status}).`, "ok");
    } else {
      showStatus(`Backend respondeu, mas com status ${response.status} em ${apiUrl}/health.`, "error");
    }
  } catch (err) {
    showStatus(`Não foi possível conectar em ${apiUrl}: ${err.message || err}.`, "error");
  } finally {
    els.testButton.disabled = false;
    els.testButton.textContent = "Testar conexão";
  }
}

function handleReset() {
  els.apiUrl.value = DEFAULT_API_BASE_URL;
  els.frontendUrl.value = DEFAULT_FRONTEND_URL;
  showStatus("Campos voltaram ao padrão de desenvolvimento — clique em Salvar para aplicar.", "ok");
}

document.addEventListener("DOMContentLoaded", () => {
  els.form = $("settings-form");
  els.apiUrl = $("api-url");
  els.frontendUrl = $("frontend-url");
  els.saveButton = $("save-button");
  els.testButton = $("test-button");
  els.resetButton = $("reset-button");
  els.status = $("status");

  els.form.addEventListener("submit", handleSave);
  els.testButton.addEventListener("click", handleTestConnection);
  els.resetButton.addEventListener("click", handleReset);

  loadCurrentValues();
});
