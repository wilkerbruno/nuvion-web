// Content script MAIN-world (Fase 2, MVP) — mascaramento de fingerprint
// básico, equivalente parcial de core/managers/anti_detect_manager.py e
// core/widgets/settings/anti_detect_section.py no app desktop.
//
// Roda em `document_start`, no mundo principal da página (declarado via
// content_scripts[].world = "MAIN" no manifest.json — recurso do Chrome
// 111+), então os overrides abaixo entram em vigor antes de qualquer script
// da própria página rodar — inclusive scripts inline, e sem esbarrar na CSP
// da página (diferente da técnica antiga de injetar uma tag <script>).
//
// Limitação conhecida (documentada no plano de migração, seção 5): isto
// mascara sinais de JavaScript, não o fingerprint de rede (TLS/JA3/HTTP2) —
// esse nível de spoofing exigiria um proxy/MITM na camada de rede, fora do
// alcance de uma extensão de navegador comum.
//
// O mascaramento continua fixo, igual para todos os usuários (não lê
// `anti_detection_settings` do backend). Isso é uma limitação real do
// Manifest V3, não só falta de tempo: um script `world: "MAIN"` não tem
// acesso a `chrome.storage`/`chrome.runtime` (só o mundo ISOLATED tem), e
// não existe forma síncrona de repassar configuração de um mundo para o
// outro antes do primeiro script da página rodar. Esta observação dizia
// "fica para a Fase 4" quando foi escrita (Fase 2) — mas o escopo de Fase 4
// que acabou sendo aprovado/executado foi diamantes, IA, notificações e
// downloads (ver docs/PLANO_MIGRACAO.md, seção 8), não configurações de
// anti-detecção. Isto permanece em aberto para uma fase futura, quando vale
// a pena investigar `chrome.scripting.executeScript` com `world: "MAIN"`
// disparado a partir de um listener de navegação (aceitando o pequeno
// atraso que isso implica em vez do zero-atraso do content script
// declarativo).
(function () {
  "use strict";

  function clampByte(value) {
    return Math.min(255, Math.max(0, Math.round(value)));
  }

  try {
    Object.defineProperty(Navigator.prototype, "webdriver", {
      get: () => false,
      configurable: true,
    });
  } catch (err) {
    console.debug("[Nuvion] Não foi possível mascarar navigator.webdriver:", err);
  }

  // Ruído leve e fixo por carregamento de página no canvas — dificulta
  // canvas fingerprinting. O deslocamento é de no máximo 1 por canal de
  // cor, imperceptível visualmente, mas suficiente para mudar o hash do
  // canvas entre sessões/abas.
  try {
    const noiseSeed = Math.random() * 2 - 1;

    const applyNoise = (imageData) => {
      const { data } = imageData;
      for (let i = 0; i < data.length; i += 4) {
        data[i] = clampByte(data[i] + noiseSeed);
        data[i + 1] = clampByte(data[i + 1] + noiseSeed);
        data[i + 2] = clampByte(data[i + 2] + noiseSeed);
      }
      return imageData;
    };

    const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData = function (...args) {
      const imageData = originalGetImageData.apply(this, args);
      return applyNoise(imageData);
    };

    const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function (...args) {
      const ctx = this.getContext("2d");
      if (ctx) {
        try {
          const imageData = originalGetImageData.call(ctx, 0, 0, this.width, this.height);
          applyNoise(imageData);
          ctx.putImageData(imageData, 0, 0);
        } catch (err) {
          console.debug("[Nuvion] Ruído de canvas ignorado em toDataURL:", err);
        }
      }
      return originalToDataURL.apply(this, args);
    };
  } catch (err) {
    console.debug("[Nuvion] Não foi possível aplicar ruído de canvas:", err);
  }
})();
