// frontend/src/components/pages/RegisterPage.jsx
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuthStore } from "../../stores";
import toast from "react-hot-toast";
import { Loader2 } from "lucide-react";

export default function RegisterPage() {
  const [form, setForm] = useState({
    username: "", password: "", email: "", name: "",
    phone: "", referral_code: "", cpf: "",
  });
  const [loading, setLoading] = useState(false);
  const { register } = useAuthStore();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await register(form);
      toast.success("Conta criada! Faça login para continuar.");
      navigate("/login");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erro ao criar conta");
    } finally {
      setLoading(false);
    }
  };

  const field = (key, label, type = "text", placeholder = "") => (
    <div>
      <label className="text-sm text-slate-300 mb-1 block">{label}</label>
      <input
        type={type}
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        placeholder={placeholder}
        className="w-full bg-[#0F172A] border border-[#334155] rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-[#2563EB]"
      />
    </div>
  );

  return (
    <div className="min-h-screen bg-[#0F172A] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-white">Criar Conta</h1>
          <p className="text-slate-400 mt-1 text-sm">Você precisa de um código de indicação</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-[#1E293B] border border-[#1E293B] rounded-2xl p-6 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            {field("name", "Nome completo", "text", "João Silva")}
            {field("username", "Usuário", "text", "joaosilva")}
          </div>
          {field("email", "Email", "email", "joao@email.com")}
          <div className="grid grid-cols-2 gap-3">
            {field("phone", "Telefone", "tel", "(11) 99999-9999")}
            {field("cpf", "CPF (opcional)", "text", "000.000.000-00")}
          </div>
          {field("password", "Senha", "password", "Mínimo 6 caracteres")}
          <div>
            <label className="text-sm text-slate-300 mb-1 block">
              Código de indicação <span className="text-red-400">*</span>
            </label>
            <input
              value={form.referral_code}
              onChange={(e) => setForm({ ...form, referral_code: e.target.value.toUpperCase() })}
              placeholder="XXXXXXXX"
              className="w-full bg-[#0F172A] border border-[#334155] rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-[#2563EB] uppercase"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-gradient-to-r from-[#1A3A5C] to-[#2563EB] text-white font-semibold py-2.5 rounded-lg hover:opacity-90 transition-opacity flex items-center justify-center gap-2 mt-2"
          >
            {loading && <Loader2 size={16} className="animate-spin" />}
            Criar conta
          </button>

          <p className="text-center text-xs text-slate-400 pt-1">
            Já tem conta?{" "}
            <Link to="/login" className="text-[#2563EB] hover:underline">
              Fazer login
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
