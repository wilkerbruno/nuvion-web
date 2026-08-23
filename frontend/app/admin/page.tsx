"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, clearTokens, getAccessToken, UserPublic } from "@/lib/api";

export default function AdminHubPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserPublic | null>(null);

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
        }
      })
      .catch(() => router.replace("/login"));
  }, [router]);

  function handleLogout() {
    clearTokens();
    router.push("/login");
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
      <div className="card card--wide">
        <div className="topbar">
          <div className="brand">
            Nuvion<span>Web</span>
          </div>
          <button className="btn-link" onClick={handleLogout}>
            Sair
          </button>
        </div>

        <div className="subtitle">Área administrativa</div>

        <nav className="nav-links">
          <Link href="/dashboard">Painel</Link>
        </nav>

        <div className="tool-grid">
          <Link href="/admin/ai-tools" className="tool-card" style={{ textDecoration: "none" }}>
            <div className="icon">🛠️</div>
            <div className="name">Ferramentas de IA</div>
            <div className="desc">
              Criar, editar e remover ferramentas do catálogo; configurar login (credenciais ou
              cookies) e o proxy usado por cada ferramenta.
            </div>
          </Link>
          <Link href="/admin/rewards" className="tool-card" style={{ textDecoration: "none" }}>
            <div className="icon">🎁</div>
            <div className="name">Recompensas</div>
            <div className="desc">
              Criar, editar, pausar e remover itens do catálogo de recompensas trocáveis por
              diamantes.
            </div>
          </Link>
        </div>

        <div className="foot-link">
          Definir o plano (Standard/Premium/VIP) de um usuário ainda não tem rota nem tela própria
          nesta versão — hoje o plano só muda quando o próprio usuário paga (ou por acesso direto
          ao banco). Uma tela de administração de usuários (trocar plano, bloquear conta) pode
          entrar numa próxima iteração.
        </div>
      </div>
    </div>
  );
}
