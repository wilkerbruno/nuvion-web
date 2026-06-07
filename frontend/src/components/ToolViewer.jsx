// frontend/src/components/ToolViewer.jsx
// Exibe o Chrome remoto via noVNC dentro de um iframe
import { useEffect, useRef, useState } from "react";

const WORKER_NOVNC_URL = import.meta.env.VITE_WORKER_NOVNC_URL || 
  "https://divisions-nuvion-worker.lcgx8u.easypanel.host";

export default function ToolViewer({ jobId, onClose }) {
  const [status, setStatus] = useState("connecting"); // connecting | ready | error
  const wsRef = useRef(null);
  const iframeRef = useRef(null);

  // noVNC URL — autoconnect=true pula a tela de login do noVNC
  const novncUrl = `${WORKER_NOVNC_URL}/vnc.html?autoconnect=true&reconnect=true&resize=scale&quality=6&compression=2`;

  useEffect(() => {
    if (!jobId) return;

    // Conecta ao WebSocket da API para aguardar confirmação do Chrome aberto
    const apiBase = import.meta.env.VITE_API_URL?.replace("https://", "wss://").replace("http://", "ws://");
    const token = localStorage.getItem("access_token");
    const ws = new WebSocket(`${apiBase}/api/worker/ws/${jobId}?token=${token}`);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === "opened" || data.type === "queued") {
        // Chrome abriu — mostrar iframe noVNC
        setStatus("ready");
      } else if (data.type === "error") {
        setStatus("error");
      }
    };

    ws.onerror = () => setStatus("error");

    return () => ws.close();
  }, [jobId]);

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 1000,
      background: "#000", display: "flex", flexDirection: "column"
    }}>
      {/* Barra superior */}
      <div style={{
        height: 40, background: "#1a1a2e", display: "flex",
        alignItems: "center", justifyContent: "space-between",
        padding: "0 16px", color: "#fff", fontSize: 14,
        flexShrink: 0
      }}>
        <span>🖥️ Chrome Remoto</span>
        <button
          onClick={onClose}
          style={{
            background: "#e74c3c", border: "none", color: "#fff",
            borderRadius: 4, padding: "4px 12px", cursor: "pointer"
          }}
        >
          Fechar
        </button>
      </div>

      {/* Conteúdo */}
      {status === "connecting" && (
        <div style={{
          flex: 1, display: "flex", alignItems: "center",
          justifyContent: "center", color: "#aaa", flexDirection: "column", gap: 12
        }}>
          <div style={{ fontSize: 32 }}>⏳</div>
          <span>Abrindo Chrome...</span>
        </div>
      )}

      {status === "error" && (
        <div style={{
          flex: 1, display: "flex", alignItems: "center",
          justifyContent: "center", color: "#e74c3c", flexDirection: "column", gap: 12
        }}>
          <div style={{ fontSize: 32 }}>❌</div>
          <span>Erro ao abrir ferramenta</span>
        </div>
      )}

      {status === "ready" && (
        <iframe
          ref={iframeRef}
          src={novncUrl}
          style={{ flex: 1, border: "none", width: "100%", height: "100%" }}
          allow="clipboard-read; clipboard-write"
          title="Chrome Remoto"
        />
      )}
    </div>
  );
}
