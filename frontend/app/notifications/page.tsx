"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError, clearTokens, getAccessToken, NotificationPublic } from "@/lib/api";

export default function NotificationsPage() {
  const router = useRouter();
  const [notifications, setNotifications] = useState<NotificationPublic[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [includeRead, setIncludeRead] = useState(false);

  function load() {
    api
      .myNotifications(includeRead)
      .then(setNotifications)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          clearTokens();
          router.replace("/login");
          return;
        }
        setError(err instanceof ApiError ? err.message : "Erro ao carregar notificações.");
      });
  }

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router, includeRead]);

  async function handleMarkRead(id: string) {
    try {
      await api.markNotificationRead(id);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao marcar como lida.");
    }
  }

  async function handleMarkAllRead() {
    try {
      await api.markAllNotificationsRead();
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao marcar todas como lidas.");
    }
  }

  async function handleDelete(id: string) {
    try {
      await api.deleteNotification(id);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao apagar notificação.");
    }
  }

  return (
    <div className="page page--top">
      <div className="card card--xwide">
        <div className="topbar">
          <div className="brand">
            Nuvion<span>Web</span>
          </div>
          <Link className="btn-link" href="/dashboard">
            Voltar ao painel
          </Link>
        </div>

        <nav className="nav-links">
          <Link href="/dashboard">Painel</Link>
          <Link href="/rewards">Diamantes</Link>
          <Link href="/ai-tools">Ferramentas de IA</Link>
          <Link href="/downloads">Downloads</Link>
        </nav>

        <div className="topbar" style={{ marginBottom: 12 }}>
          <div className="subtitle" style={{ margin: 0 }}>
            Notificações
          </div>
          <button className="btn-link" onClick={handleMarkAllRead}>
            Marcar todas como lidas
          </button>
        </div>

        {error && <div className="error">{error}</div>}

        <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16, fontSize: 13 }}>
          <input
            type="checkbox"
            checked={includeRead}
            onChange={(e) => setIncludeRead(e.target.checked)}
          />
          Mostrar já lidas
        </label>

        {!notifications ? (
          <div className="subtitle">Carregando...</div>
        ) : notifications.length === 0 ? (
          <div className="empty-state">Nenhuma notificação por aqui.</div>
        ) : (
          <div className="notification-list">
            {notifications.map((n) => (
              <div
                key={n.id}
                className={`notification-row ${!n.is_read ? "notification-row--unread" : ""}`}
              >
                <div className="icon">{n.icon}</div>
                <div className="body">
                  <div className="title">{n.title}</div>
                  <div className="message">{n.message}</div>
                  <div className="meta">{new Date(n.created_at).toLocaleString("pt-BR")}</div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {!n.is_read && (
                    <button className="btn-link" onClick={() => handleMarkRead(n.id)}>
                      Marcar como lida
                    </button>
                  )}
                  <button
                    className="btn-link"
                    style={{ color: "var(--danger)" }}
                    onClick={() => handleDelete(n.id)}
                  >
                    Apagar
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
