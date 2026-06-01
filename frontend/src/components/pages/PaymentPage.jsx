// frontend/src/components/pages/PaymentPage.jsx
import { useState } from "react";
import api from "../../lib/api";
import toast from "react-hot-toast";
import { Loader2, Copy, CheckCircle } from "lucide-react";

const PLANS = [
  { id: "Standard", label: "Standard", price: "R$ 97,00 / mês", color: "#0284C7" },
  { id: "Premium",  label: "Premium",  price: "R$ 70,00 / mês", color: "#047857" },
  { id: "VIP",      label: "VIP",      price: "Gratuito",        color: "#B45309" },
];

export default function PaymentPage() {
  const [plan, setPlan] = useState("Standard");
  const [loading, setLoading] = useState(false);
  const [pix, setPix] = useState(null);
  const [copied, setCopied] = useState(false);

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const { data } = await api.post("/payments/pix", { plan });
      setPix(data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erro ao gerar PIX");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(pix.qr_code);
    setCopied(true);
    toast.success("Código copiado!");
    setTimeout(() => setCopied(false), 3000);
  };

  return (
    <div className="p-6 max-w-xl mx-auto">
      <h2 className="text-2xl font-bold text-white mb-1">Ativação de Conta</h2>
      <p className="text-slate-400 text-sm mb-6">Escolha um plano e pague via PIX</p>

      {/* Plan selector */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        {PLANS.map((p) => (
          <button
            key={p.id}
            onClick={() => { setPlan(p.id); setPix(null); }}
            className="rounded-xl border p-4 text-left transition-all"
            style={{
              borderColor: plan === p.id ? p.color : "#1E293B",
              background: plan === p.id ? `${p.color}15` : "#1E293B",
            }}
          >
            <p className="font-bold text-white text-sm">{p.label}</p>
            <p className="text-xs mt-1" style={{ color: p.color }}>{p.price}</p>
          </button>
        ))}
      </div>

      {/* Generate button */}
      {!pix && (
        <button
          onClick={handleGenerate}
          disabled={loading}
          className="w-full bg-gradient-to-r from-[#1A3A5C] to-[#2563EB] text-white font-semibold py-3 rounded-xl hover:opacity-90 transition-opacity flex items-center justify-center gap-2"
        >
          {loading && <Loader2 size={16} className="animate-spin" />}
          Gerar PIX {plan}
        </button>
      )}

      {/* PIX result */}
      {pix && (
        <div className="bg-[#1E293B] border border-[#1E293B] rounded-2xl p-5 space-y-4">
          <div className="text-center">
            <p className="text-white font-semibold mb-1">PIX gerado!</p>
            <p className="text-slate-400 text-sm">
              Valor: <strong className="text-white">R$ {pix.amount?.toFixed(2)}</strong>
            </p>
          </div>

          {pix.qr_code_image && (
            <div className="flex justify-center">
              <img
                src={`data:image/png;base64,${pix.qr_code_image}`}
                alt="QR Code PIX"
                className="w-48 h-48 rounded-xl"
              />
            </div>
          )}

          <div className="bg-[#0F172A] rounded-lg p-3 text-xs text-slate-400 font-mono break-all">
            {pix.qr_code?.slice(0, 60)}...
          </div>

          <button
            onClick={handleCopy}
            className="w-full flex items-center justify-center gap-2 bg-[#0F172A] border border-[#334155] text-white text-sm py-2.5 rounded-lg hover:border-[#2563EB] transition-colors"
          >
            {copied ? <CheckCircle size={15} className="text-green-400" /> : <Copy size={15} />}
            {copied ? "Copiado!" : "Copiar código PIX"}
          </button>

          <button
            onClick={() => setPix(null)}
            className="w-full text-slate-400 text-sm hover:text-white transition-colors"
          >
            Gerar novamente
          </button>
        </div>
      )}
    </div>
  );
}
