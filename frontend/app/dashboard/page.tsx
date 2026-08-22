"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError, clearTokens, DashboardSummary, getAccessToken } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }

    api
      .dashboard()
      .then(setData)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          clearTokens();
          router.replace("/login");
          return;
        }
        setError(err instanceof ApiError ? err.message : "Erro ao carregar o painel.");
      });

    api
      .unreadNotificationCount()
      .then((r) => setUnreadCount(r.unread_count))
      .catch(() => undefined);
  }, [router]);

  function handleLogout() {
    clearTokens();
    router.push("/login");
  }

  if (error) {
    return (
      <div className="page">
        <div className="card error">{error}</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="page">
        <div className="subtitle">Carregando...</div>
      </div>
    );
  }

  const { user, payment_status } = data;

  return (
    <div className="page page--top">
      <div className="card card--wide">
        <div className="topbar">
          <div className="brand">
            Nuvion<span>Web</span>
          </div>
          <button className="btn-link" onClick={handleLogout}>
            Sair
          </button>
        </div>

        <div className="subtitle">
          Olá, {user.name} — @{user.username}
        </div>

        <nav className="nav-links">
          <Link href="/rewards">Diamantes</Link>
          <Link href="/ai-tools">Ferramentas de IA</Link>
          <Link href="/notifications">
            Notificações
            {unreadCount > 0 && <span className="nav-badge">{unreadCount}</span>}
          </Link>
          <Link href="/downloads">Downloads</Link>
        </nav>

        {data.is_blocked && <div className="error">{data.block_message}</div>}

        <div className="stat-row">
          <div className="stat">
            <div className="k">Plano</div>
            <div className="v">{user.category}</div>
          </div>
          <div className="stat">
            <div className="k">Status da conta</div>
            <div className="v">{user.status}</div>
          </div>
          <div className="stat">
            <div className="k">Assinatura</div>
            <div className="v">{payment_status.status}</div>
          </div>
        </div>

        <div className="field">
          <div className="label">Código de indicação</div>
          <div className="input" style={{ userSelect: "all" }}>
            {user.referral_code}
          </div>
        </div>

        <Link className="btn" href="/payments" style={{ display: "block", textAlign: "center" }}>
          Assinatura e pagamentos
        </Link>
      </div>
    </div>
  );
}
