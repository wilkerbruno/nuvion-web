// frontend/src/components/layout/Layout.jsx
import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuthStore, useNotifStore } from "../../stores";
import {
  LayoutGrid, List, Star, MessageSquare, Image, Code2,
  PenLine, BarChart2, Bell, Settings, LogOut, Shield, Menu, X,
} from "lucide-react";
import clsx from "clsx";

const NAV = [
  { to: "/panel",    label: "Painel de IAs", icon: LayoutGrid },
  { to: "/settings", label: "Configurações",  icon: Settings },
  { to: "/payment",  label: "Pagamentos",     icon: Star },
];

export default function Layout({ children }) {
  const [open, setOpen] = useState(true);
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, isAdmin } = useAuthStore();
  const { unreadCount } = useNotifStore();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="flex h-screen bg-[#0F172A] text-white overflow-hidden">
      {/* Sidebar */}
      <aside
        className={clsx(
          "flex flex-col transition-all duration-300 bg-gradient-to-b from-[#1A3A5C] to-[#2563EB] shrink-0",
          open ? "w-64" : "w-16"
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-5 border-b border-white/20">
          {open && (
            <span className="font-bold text-lg tracking-tight">Nuvion Browser</span>
          )}
          <button onClick={() => setOpen(!open)} className="text-white/70 hover:text-white">
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        {/* Nav links */}
        <nav className="flex-1 py-4 space-y-1 px-2">
          {NAV.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className={clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                location.pathname === to
                  ? "bg-white/20 text-white border-l-4 border-white"
                  : "text-white/70 hover:bg-white/10 hover:text-white"
              )}
            >
              <Icon size={18} className="shrink-0" />
              {open && <span>{label}</span>}
            </Link>
          ))}

          {isAdmin() && (
            <Link
              to="/admin"
              className={clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors mt-4",
                location.pathname === "/admin"
                  ? "bg-white/20 text-white border-l-4 border-white"
                  : "text-white/70 hover:bg-white/10 hover:text-white"
              )}
            >
              <Shield size={18} className="shrink-0" />
              {open && <span>Administração</span>}
            </Link>
          )}
        </nav>

        {/* User footer */}
        <div className="p-3 border-t border-white/20">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center text-sm font-bold shrink-0">
              {user?.name?.[0]?.toUpperCase() || "U"}
            </div>
            {open && (
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{user?.name}</p>
                <p className="text-xs text-white/60 truncate">{user?.account_type}</p>
              </div>
            )}
            {open && (
              <button
                onClick={handleLogout}
                className="text-white/60 hover:text-white"
                title="Sair"
              >
                <LogOut size={16} />
              </button>
            )}
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex items-center justify-between px-6 py-3 bg-[#0F172A] border-b border-[#1E293B]">
          <h1 className="text-sm font-medium text-slate-400 capitalize">
            {location.pathname.replace("/", "") || "painel"}
          </h1>
          <div className="flex items-center gap-3">
            <Link to="/settings" className="relative text-slate-400 hover:text-white">
              <Bell size={20} />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] rounded-full w-4 h-4 flex items-center justify-center">
                  {unreadCount > 9 ? "9+" : unreadCount}
                </span>
              )}
            </Link>
          </div>
        </header>

        {/* Page */}
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
