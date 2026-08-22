"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  api,
  ApiError,
  clearTokens,
  getAccessToken,
  RewardBalance,
  RewardCatalogItem,
} from "@/lib/api";

export default function RewardsPage() {
  const router = useRouter();
  const [balance, setBalance] = useState<RewardBalance | null>(null);
  const [catalog, setCatalog] = useState<RewardCatalogItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [claimingId, setClaimingId] = useState<string | null>(null);

  function loadAll() {
    Promise.all([api.myRewards(), api.rewardsCatalog()])
      .then(([b, c]) => {
        setBalance(b);
        setCatalog(c);
      })
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
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  async function handleClaim(rewardId: string) {
    setClaimingId(rewardId);
    setError(null);
    setNotice(null);
    try {
      const result = await api.claimReward(rewardId);
      setNotice(result.message);
      loadAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao resgatar recompensa.");
    } finally {
      setClaimingId(null);
    }
  }

  if (error && !balance) {
    return (
      <div className="page">
        <div className="card error">{error}</div>
      </div>
    );
  }

  if (!balance || !catalog) {
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
          <Link className="btn-link" href="/dashboard">
            Voltar ao painel
          </Link>
        </div>

        <nav className="nav-links">
          <Link href="/dashboard">Painel</Link>
          <Link href="/ai-tools">Ferramentas de IA</Link>
          <Link href="/notifications">Notificações</Link>
          <Link href="/downloads">Downloads</Link>
        </nav>

        <div className="subtitle">Diamantes e recompensas</div>

        {error && <div className="error">{error}</div>}
        {notice && <div className="success-box">{notice}</div>}

        <div className="diamond-balance">
          <div className="amount">💎 {balance.diamonds}</div>
          <div className="unit">diamantes disponíveis</div>
        </div>

        <div className="field">
          <div className="label">
            Indique amigos com seu código e ganhe {balance.referral_reward} diamantes por cadastro
          </div>
          <div className="input" style={{ userSelect: "all" }}>
            {balance.referral_code}
          </div>
        </div>

        <div className="section-title">Catálogo de recompensas</div>
        <div className="reward-grid">
          {catalog.map((reward) => (
            <div key={reward.id} className="reward-card">
              <div className="icon">{reward.icon}</div>
              <div className="title">{reward.title}</div>
              <div className="desc">{reward.description}</div>
              <div className="points">💎 {reward.points}</div>
              <button
                className="btn-secondary"
                disabled={
                  reward.already_claimed ||
                  !reward.available ||
                  balance.diamonds < reward.points ||
                  claimingId === reward.id
                }
                onClick={() => handleClaim(reward.id)}
                style={{ marginTop: 10 }}
              >
                {reward.already_claimed
                  ? "Já resgatado"
                  : claimingId === reward.id
                    ? "Resgatando..."
                    : "Resgatar"}
              </button>
            </div>
          ))}
        </div>

        <div className="section-title">Histórico de transações</div>
        {balance.transactions.length === 0 ? (
          <div className="empty-state">Nenhuma transação ainda.</div>
        ) : (
          <div className="payment-list">
            {balance.transactions.map((tx) => (
              <div key={tx.id} className="payment-row">
                <div>
                  <div className="desc">{tx.description}</div>
                  <div className="meta">{new Date(tx.timestamp).toLocaleString("pt-BR")}</div>
                </div>
                <div className={tx.diamonds >= 0 ? "badge badge--confirmado" : "badge badge--atrasado"}>
                  {tx.diamonds >= 0 ? "+" : ""}
                  {tx.diamonds} 💎
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
