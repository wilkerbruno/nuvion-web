// frontend/src/components/pages/ExtensionPage.jsx
import { useState } from "react";
import { useAuthStore } from "../../stores";
import toast from "react-hot-toast";
import { Copy, Check, Chrome, Wifi, WifiOff, ExternalLink } from "lucide-react";

const WS_URL = "wss://divisions-nuvion-web-api.lcgx8u.easypanel.host/api/extension/ws";

export default function ExtensionPage() {
  const accessToken = useAuthStore((s) => s.accessToken);
  const [copied, setCopied] = useState(null);

  const copy = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopied(key);
    toast.success("Copiado!");
    setTimeout(() => setCopied(null), 2000);
  };

  const CopyBtn = ({ text, label, id }) => (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <label style={{ fontSize: 12, color: "#94a3b8" }}>{label}</label>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          readOnly
          value={text}
          style={{
            flex: 1, padding: "8px 10px",
            background: "#1e293b", border: "1px solid #334155",
            borderRadius: 6, color: "#e2e8f0", fontSize: 12,
            fontFamily: "monospace",
          }}
        />
        <button
          onClick={() => copy(text, id)}
          style={{
            padding: "8px 12px", background: copied === id ? "#22c55e" : "#2563eb",
            border: "none", borderRadius: 6, color: "#fff", cursor: "pointer",
            display: "flex", alignItems: "center", gap: 4, fontSize: 12,
            transition: "background 0.2s",
          }}
        >
          {copied === id ? <Check size={14} /> : <Copy size={14} />}
          {copied === id ? "Copiado" : "Copiar"}
        </button>
      </div>
    </div>
  );

  return (
    <div style={{ padding: 32, maxWidth: 600, margin: "0 auto", color: "#e2e8f0" }}>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
          <Chrome size={28} color="#2563eb" />
          <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>Extensão Chrome</h1>
        </div>
        <p style={{ color: "#94a3b8", fontSize: 14, lineHeight: 1.6 }}>
          A extensão abre as ferramentas diretamente no seu Chrome, com login automático
          e proxy configurado — sem VNC, sem lag, com clipboard funcionando normalmente.
        </p>
      </div>

      {/* Passos */}
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

        {/* Passo 1 */}
        <div style={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 12, padding: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
            <span style={{
              width: 24, height: 24, background: "#2563eb", borderRadius: "50%",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 12, fontWeight: 700, flexShrink: 0
            }}>1</span>
            <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>Instalar a extensão</h3>
          </div>
          <p style={{ color: "#94a3b8", fontSize: 13, marginBottom: 12 }}>
            Abra <code style={{ color: "#60a5fa" }}>chrome://extensions</code>, ative o
            <strong style={{ color: "#e2e8f0" }}> Modo desenvolvedor</strong> e clique em
            <strong style={{ color: "#e2e8f0" }}> "Carregar sem compactação"</strong>.
          </p>
          <p style={{ color: "#64748b", fontSize: 12 }}>
            Selecione a pasta da extensão Nuvion que você baixou.
          </p>
        </div>

        {/* Passo 2 */}
        <div style={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 12, padding: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
            <span style={{
              width: 24, height: 24, background: "#2563eb", borderRadius: "50%",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 12, fontWeight: 700, flexShrink: 0
            }}>2</span>
            <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>Configurar a extensão</h3>
          </div>
          <p style={{ color: "#94a3b8", fontSize: 13, marginBottom: 16 }}>
            Copie os valores abaixo e cole no popup da extensão.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <CopyBtn
              label="Token de acesso"
              text={accessToken || ""}
              id="token"
            />
            <CopyBtn
              label="URL do servidor"
              text={WS_URL}
              id="wsurl"
            />
          </div>
        </div>

        {/* Passo 3 */}
        <div style={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 12, padding: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
            <span style={{
              width: 24, height: 24, background: "#2563eb", borderRadius: "50%",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 12, fontWeight: 700, flexShrink: 0
            }}>3</span>
            <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>Conectar</h3>
          </div>
          <p style={{ color: "#94a3b8", fontSize: 13 }}>
            Clique no ícone da extensão na barra do Chrome, cole o token e a URL,
            e clique em <strong style={{ color: "#e2e8f0" }}>Conectar</strong>.
            O badge ficará <span style={{ color: "#22c55e", fontWeight: 600 }}>ON</span> quando conectado.
          </p>
        </div>

        {/* Aviso */}
        <div style={{
          background: "#1a2744", border: "1px solid #2563eb33",
          borderRadius: 8, padding: 14, fontSize: 12, color: "#93c5fd",
          lineHeight: 1.6,
        }}>
          💡 Após conectar, ao clicar em qualquer ferramenta o Chrome abrirá
          uma janela local na sua máquina com login automático e proxy configurado,
          exatamente como na versão desktop.
        </div>
      </div>
    </div>
  );
}
