"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  api,
  ApiError,
  clearTokens,
  getAccessToken,
  PlanCategory,
  UserPublic,
  UserStatus,
} from "@/lib/api";

const PLAN_OPTIONS: PlanCategory[] = ["Standard", "Premium", "VIP"];
const STATUS_OPTIONS: UserStatus[] = ["Ativo", "Inativo", "Cancelado", "Bloqueado"];

function statusBadgeClass(status: string): string {
  const map: Record<string, string> = {
    Ativo: "badge--confirmado",
    Inativo: "badge--pendente",
    Cancelado: "badge--atrasado",
    Bloqueado: "badge--cancelado",
  };
  return `badge ${map[status] ?? "badge--pendente"}`;
}

export default function AdminUsersPage() {
  const router = useRouter();
  const [me, setMe] = useState<UserPublic | null>(null);
  const [users, setUsers] = useState<UserPublic[] | null>(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);

  function loadUsers(query?: string) {
    api
      .adminUsers(query || undefined)
      .then(setUsers)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          clearTokens();
          router.replace("/login");
          return;
        }
        setError(err instanceof ApiError ? err.message : "Erro ao carregar usuários.");
      });
  }

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }
    api
      .me()
      .then((u) => {
        setMe(u);
        if (u.account_type !== "Admin") {
          router.replace("/dashboard");
          return;
        }
        loadUsers();
      })
      .catch(() => router.replace("/login"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  useEffect(() => {
    if (!getAccessToken() || !me) return;
    const timeout = setTimeout(() => loadUsers(search), 300);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  async function handleCategoryChange(userId: string, category: PlanCategory) {
    setSavingId(userId);
    setError(null);
    try {
      const updated = await api.updateAdminUser(userId, { category });
      setUsers((prev) => (prev ? prev.map((u) => (u.id === userId ? updated : u)) : prev));
      setNotice(`Plano de ${updated.username} atualizado para ${updated.category}.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao atualizar plano.");
    } finally {
      setSavingId(null);
    }
  }

  async function handleStatusChange(userId: string, statusValue: UserStatus) {
    setSavingId(userId);
    setError(null);
    try {
      const updated = await api.updateAdminUser(userId, { status: statusValue });
      setUsers((prev) => (prev ? prev.map((u) => (u.id === userId ? updated : u)) : prev));
      setNotice(`Status de ${updated.username} atualizado para ${updated.status}.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao atualizar status.");
    } finally {
      setSavingId(null);
    }
  }

  if (!me || me.account_type !== "Admin") {
    return (
      <div className="page">
        <div className="subtitle">Carregando...</div>
      </div>
    );
  }

  return (
    <div className="page page--top">
      <div className="card card--xwide">
        <div className="topbar">
          <div className="brand">
            Nuvion<span>Web</span>
          </div>
          <Link className="btn-link" href="/admin">
            ← Área administrativa
          </Link>
        </div>

        <div className="subtitle">Usuários — administração</div>
        <div className="subtitle">
          Defina o plano de cada conta ou bloqueie o acesso (status &quot;Bloqueado&quot;) —
          alterações valem na hora, inclusive pra sessões já logadas.
        </div>

        {error && <div className="error">{error}</div>}
        {notice && <div className="success-box">{notice}</div>}

        <div className="filter-row">
          <input
            className="input"
            placeholder="Buscar por usuário, nome ou email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {!users ? (
          <div className="subtitle">Carregando...</div>
        ) : users.length === 0 ? (
          <div className="empty-state">Nenhum usuário encontrado.</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Usuário</th>
                  <th>Nome</th>
                  <th>Email</th>
                  <th>Tipo de conta</th>
                  <th>Plano</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td>{user.username}</td>
                    <td>{user.name}</td>
                    <td>{user.email}</td>
                    <td>{user.account_type}</td>
                    <td>
                      <select
                        className="input"
                        value={user.category}
                        disabled={savingId === user.id}
                        onChange={(e) => handleCategoryChange(user.id, e.target.value as PlanCategory)}
                      >
                        {PLAN_OPTIONS.map((p) => (
                          <option key={p} value={p}>
                            {p}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <select
                        className="input"
                        value={user.status}
                        disabled={savingId === user.id}
                        onChange={(e) => handleStatusChange(user.id, e.target.value as UserStatus)}
                      >
                        {STATUS_OPTIONS.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                      <span className={statusBadgeClass(user.status)}>{user.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
