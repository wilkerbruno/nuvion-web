"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  api,
  ApiError,
  clearTokens,
  getAccessToken,
  RewardAdminItem,
  RewardCreatePayload,
  UserPublic,
} from "@/lib/api";

type RewardFormState = {
  icon: string;
  title: string;
  description: string;
  points: string;
  available: boolean;
};

const EMPTY_FORM: RewardFormState = {
  icon: "🎁",
  title: "",
  description: "",
  points: "",
  available: true,
};

export default function AdminRewardsPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserPublic | null>(null);
  const [rewards, setRewards] = useState<RewardAdminItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [form, setForm] = useState<RewardFormState>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function loadRewards() {
    api
      .adminRewards()
      .then(setRewards)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          clearTokens();
          router.replace("/login");
          return;
        }
        setError(err instanceof ApiError ? err.message : "Erro ao carregar recompensas.");
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
        setUser(u);
        if (u.account_type !== "Admin") {
          router.replace("/dashboard");
          return;
        }
        loadRewards();
      })
      .catch(() => router.replace("/login"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  function resetForm() {
    setForm(EMPTY_FORM);
    setEditingId(null);
  }

  function startEdit(reward: RewardAdminItem) {
    setEditingId(reward.id);
    setForm({
      icon: reward.icon,
      title: reward.title,
      description: reward.description,
      points: String(reward.points),
      available: reward.available,
    });
    if (typeof window !== "undefined") window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    const points = Number(form.points);
    if (!Number.isFinite(points) || points <= 0) {
      setError("Pontos (diamantes) precisa ser um número maior que zero.");
      setSaving(false);
      return;
    }
    const payload: RewardCreatePayload = {
      icon: form.icon || "🎁",
      title: form.title,
      description: form.description,
      points,
      available: form.available,
    };
    try {
      if (editingId) {
        await api.updateReward(editingId, payload);
        setNotice("Recompensa atualizada.");
      } else {
        await api.createReward(payload);
        setNotice("Recompensa criada.");
      }
      resetForm();
      loadRewards();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao salvar recompensa.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(rewardId: string) {
    try {
      await api.deleteReward(rewardId);
      if (editingId === rewardId) resetForm();
      loadRewards();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao remover recompensa.");
    }
  }

  async function handleToggleAvailable(reward: RewardAdminItem) {
    try {
      const updated = await api.updateReward(reward.id, { available: !reward.available });
      setRewards((prev) => (prev ? prev.map((r) => (r.id === reward.id ? updated : r)) : prev));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao atualizar disponibilidade.");
    }
  }

  if (!user || user.account_type !== "Admin") {
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

        <div className="subtitle">Recompensas — administração</div>

        {error && <div className="error">{error}</div>}
        {notice && <div className="success-box">{notice}</div>}

        <div className="section-title">{editingId ? "Editar recompensa" : "Nova recompensa"}</div>
        <form className="inline-form" onSubmit={handleSubmit}>
          <input
            className="input"
            placeholder="Ícone (emoji, ex.: 🎁)"
            maxLength={16}
            value={form.icon}
            onChange={(e) => setForm({ ...form, icon: e.target.value })}
            style={{ maxWidth: 120 }}
          />
          <input
            className="input"
            placeholder="Título"
            required
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
          <input
            className="input"
            placeholder="Descrição"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
          <input
            className="input"
            placeholder="Custo em diamantes"
            required
            type="number"
            min={1}
            value={form.points}
            onChange={(e) => setForm({ ...form, points: e.target.value })}
          />
          <label className="subtitle" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input
              type="checkbox"
              checked={form.available}
              onChange={(e) => setForm({ ...form, available: e.target.checked })}
            />
            Disponível para resgate
          </label>
          <div style={{ display: "flex", gap: 10 }}>
            <button className="btn" type="submit" disabled={saving}>
              {saving ? "Salvando..." : editingId ? "Salvar alterações" : "Criar recompensa"}
            </button>
            {editingId && (
              <button className="btn-secondary" type="button" onClick={resetForm}>
                Cancelar edição
              </button>
            )}
          </div>
        </form>

        <div className="section-title">Catálogo ({rewards?.length ?? 0})</div>
        {!rewards ? (
          <div className="subtitle">Carregando...</div>
        ) : rewards.length === 0 ? (
          <div className="empty-state">Nenhuma recompensa cadastrada ainda.</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Ícone</th>
                  <th>Título</th>
                  <th>Descrição</th>
                  <th>Diamantes</th>
                  <th>Disponível</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody>
                {rewards.map((reward) => (
                  <tr key={reward.id}>
                    <td>{reward.icon}</td>
                    <td>{reward.title}</td>
                    <td>{reward.description}</td>
                    <td>💎 {reward.points}</td>
                    <td>
                      <button className="btn-link" onClick={() => handleToggleAvailable(reward)}>
                        {reward.available ? "Sim (clique p/ pausar)" : "Não (clique p/ ativar)"}
                      </button>
                    </td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      <button className="btn-link" onClick={() => startEdit(reward)}>
                        Editar
                      </button>{" "}
                      <button
                        className="btn-link"
                        style={{ color: "var(--danger)" }}
                        onClick={() => handleDelete(reward.id)}
                      >
                        Remover
                      </button>
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
