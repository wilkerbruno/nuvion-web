// frontend/src/components/pages/SettingsPage.jsx
import { useEffect, useState } from "react";
import { useAuthStore, useNotifStore } from "../../stores";
import api from "../../lib/api";
import toast from "react-hot-toast";
import { Bell, User, LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";

export default function SettingsPage() {
  const { user, logout } = useAuthStore();
  const { notifications, fetchNotifications, markRead, markAllRead, unreadCount } = useNotifStore();
  const navigate = useNavigate();
  const [tab, setTab] = useState("perfil");

  useEffect(() => {
    if (tab === "notificacoes") fetchNotifications();
  }, [tab]);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="flex h-full">
      {/* Settings sidebar */}
      <aside className="w-52 bg-[#0B1120] border-r border-[#1E293B] py-4 px-2">
        {[
          { id: "perfil", label: "Perfil", icon: User },
          { id: "notificacoes", label: "Notificações", icon: Bell },
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium mb-0.5 transition-colors ${
              tab === id ? "bg-[#2563EB] text-white" : "text-slate-400 hover:bg-[#1E293B] hover:text-white"
            }`}
          >
            <Icon size={16} />
            {label}
            {id === "notificacoes" && unreadCount > 0 && (
              <span className="ml-auto bg-red-500 text-white text-[10px] rounded-full w-4 h-4 flex items-center justify-center">
                {unreadCount}
              </span>
            )}
          </button>
        ))}

        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium mt-4 text-red-400 hover:bg-[#1E293B] transition-colors"
        >
          <LogOut size={16} /> Sair
        </button>
      </aside>

      {/* Content */}
      <div className="flex-1 p-6 overflow-auto">
        {tab === "perfil" && (
          <div className="max-w-md">
            <h2 className="text-xl font-bold text-white mb-4">Meu Perfil</h2>
            <div className="bg-[#1E293B] rounded-2xl p-5 space-y-3">
              {[
                ["Nome", user?.name],
                ["Usuário", user?.username],
                ["Email", user?.email],
                ["Telefone", user?.phone || "-"],
                ["Tipo de conta", user?.account_type],
                ["Status", user?.status],
                ["Código de indicação", user?.referral_code || "-"],
              ].map(([label, value]) => (
                <div key={label} className="flex justify-between items-center py-2 border-b border-[#0F172A] last:border-0">
                  <span className="text-slate-400 text-sm">{label}</span>
                  <span className="text-white text-sm font-medium">{value}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === "notificacoes" && (
          <div className="max-w-lg">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-white">Notificações</h2>
              {unreadCount > 0 && (
                <button onClick={markAllRead} className="text-sm text-[#2563EB] hover:underline">
                  Marcar todas como lidas
                </button>
              )}
            </div>
            <div className="space-y-2">
              {notifications.length === 0 ? (
                <p className="text-slate-500 text-sm">Nenhuma notificação.</p>
              ) : (
                notifications.map((n) => (
                  <div
                    key={n.id}
                    onClick={() => !n.is_read && markRead(n.id)}
                    className={`flex gap-3 p-4 rounded-xl border cursor-pointer transition-colors ${
                      n.is_read ? "bg-[#1E293B] border-[#1E293B]" : "bg-[#1A3A5C] border-[#2563EB]"
                    }`}
                  >
                    <span className="text-xl shrink-0">{n.icon || "🔔"}</span>
                    <div>
                      <p className="text-white text-sm font-medium">{n.title}</p>
                      <p className="text-slate-400 text-xs mt-0.5">{n.message}</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


// frontend/src/components/pages/AdminPage.jsx — exportado no mesmo arquivo para simplicidade

export function AdminPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [broadcast, setBroadcast] = useState({ title: "", message: "" });

  useEffect(() => {
    api.get("/admin/users").then(({ data }) => setUsers(data)).finally(() => setLoading(false));
  }, []);

  const handleBroadcast = async (e) => {
    e.preventDefault();
    try {
      await api.post("/admin/broadcast", { ...broadcast, priority: "normal", icon: "📢" });
      toast.success("Notificação enviada para todos!");
      setBroadcast({ title: "", message: "" });
    } catch {
      toast.error("Erro ao enviar notificação");
    }
  };

  const handleStatusChange = async (userId, status) => {
    try {
      await api.patch(`/admin/users/${userId}`, { status });
      setUsers((prev) => prev.map((u) => u.id === userId ? { ...u, status } : u));
      toast.success("Usuário atualizado");
    } catch {
      toast.error("Erro ao atualizar usuário");
    }
  };

  return (
    <div className="p-6 space-y-8 max-w-5xl">
      <h2 className="text-2xl font-bold text-white">Administração</h2>

      {/* Broadcast */}
      <section>
        <h3 className="text-lg font-semibold text-white mb-3">Enviar notificação global</h3>
        <form onSubmit={handleBroadcast} className="bg-[#1E293B] rounded-2xl p-4 space-y-3 max-w-lg">
          <input
            value={broadcast.title}
            onChange={(e) => setBroadcast({ ...broadcast, title: e.target.value })}
            placeholder="Título"
            className="w-full bg-[#0F172A] border border-[#334155] rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-[#2563EB]"
            required
          />
          <textarea
            value={broadcast.message}
            onChange={(e) => setBroadcast({ ...broadcast, message: e.target.value })}
            placeholder="Mensagem"
            rows={3}
            className="w-full bg-[#0F172A] border border-[#334155] rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-[#2563EB] resize-none"
            required
          />
          <button type="submit" className="bg-[#2563EB] text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-[#1d4ed8] transition-colors">
            Enviar para todos
          </button>
        </form>
      </section>

      {/* Users table */}
      <section>
        <h3 className="text-lg font-semibold text-white mb-3">Usuários ({users.length})</h3>
        <div className="bg-[#1E293B] rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#0F172A]">
                {["Nome", "Usuário", "Email", "Tipo", "Status", "Ação"].map((h) => (
                  <th key={h} className="text-left px-4 py-3 text-slate-400 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-[#0F172A] hover:bg-[#0F172A] transition-colors">
                  <td className="px-4 py-3 text-white">{u.name}</td>
                  <td className="px-4 py-3 text-slate-400">@{u.username}</td>
                  <td className="px-4 py-3 text-slate-400 text-xs">{u.email}</td>
                  <td className="px-4 py-3 text-slate-300">{u.account_type}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                      u.status === "Ativo" ? "bg-green-900 text-green-300" : "bg-red-900 text-red-300"
                    }`}>
                      {u.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <select
                      value={u.status}
                      onChange={(e) => handleStatusChange(u.id, e.target.value)}
                      className="bg-[#0F172A] border border-[#334155] text-white text-xs rounded px-2 py-1"
                    >
                      <option>Ativo</option>
                      <option>Inativo</option>
                      <option>Bloqueado</option>
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}


// frontend/src/components/pages/NotFoundPage.jsx

export function NotFoundPage() {
  return (
    <div className="min-h-screen bg-[#0F172A] flex items-center justify-center text-center">
      <div>
        <p className="text-6xl font-bold text-[#2563EB]">404</p>
        <p className="text-white text-xl mt-2">Página não encontrada</p>
        <a href="/panel" className="mt-4 inline-block text-[#2563EB] hover:underline text-sm">
          Voltar ao painel
        </a>
      </div>
    </div>
  );
}
