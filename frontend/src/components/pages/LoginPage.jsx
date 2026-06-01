// frontend/src/components/pages/LoginPage.jsx
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuthStore } from "../../stores";
import toast from "react-hot-toast";
import { Loader2 } from "lucide-react";

export default function LoginPage() {
  const [form, setForm] = useState({ username: "", password: "" });
  const [loading, setLoading] = useState(false);
  const { login } = useAuthStore();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(form.username, form.password);
      toast.success("Login realizado!");
      navigate("/panel");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Credenciais inválidas");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0F172A] flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white">Nuvion Browser</h1>
          <p className="text-slate-400 mt-1 text-sm">Entre na sua conta</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-[#1E293B] border border-[#1E293B] rounded-2xl p-6 space-y-4">
          <div>
            <label className="text-sm text-slate-300 mb-1 block">Usuário</label>
            <input
              type="text"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              className="w-full bg-[#0F172A] border border-[#334155] rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-[#2563EB]"
              placeholder="seu_usuario"
              required
            />
          </div>
          <div>
            <label className="text-sm text-slate-300 mb-1 block">Senha</label>
            <input
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className="w-full bg-[#0F172A] border border-[#334155] rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-[#2563EB]"
              placeholder="••••••••"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-gradient-to-r from-[#1A3A5C] to-[#2563EB] text-white font-semibold py-2.5 rounded-lg hover:opacity-90 transition-opacity flex items-center justify-center gap-2"
          >
            {loading && <Loader2 size={16} className="animate-spin" />}
            Entrar
          </button>

          <div className="flex justify-between text-xs text-slate-400 pt-1">
            <Link to="/register" className="hover:text-white">Criar conta</Link>
            <a href="#" className="hover:text-white">Esqueci a senha</a>
          </div>
        </form>
      </div>
    </div>
  );
}
