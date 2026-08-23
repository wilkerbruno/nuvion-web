"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AIToolPublic, api, ApiError, clearTokens, getAccessToken, UserPublic } from "@/lib/api";

export default function AIToolsPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserPublic | null>(null);
  const [tools, setTools] = useState<AIToolPublic[] | null>(null);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [error, setError] = useState<string | null>(null);

  function loadTools() {
    api
      .aiTools({ category: category || undefined, search: search || undefined })
      .then(setTools)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          clearTokens();
          router.replace("/login");
          return;
        }
        setError(err instanceof ApiError ? err.message : "Erro ao carregar ferramentas.");
      });
  }

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }
    api.me().then(setUser).catch(() => undefined);
    loadTools();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  useEffect(() => {
    if (!getAccessToken()) return;
    const timeout = setTimeout(loadTools, 300);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, category]);

  async function handleToggleFavorite(toolId: string) {
    try {
      await api.toggleFavorite(toolId);
      loadTools();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao favoritar.");
    }
  }

  const isAdmin = user?.account_type === "Admin";

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
          <Link href="/notifications">Notificações</Link>
          <Link href="/downloads">Downloads</Link>
          {isAdmin && <Link href="/admin">Área administrativa</Link>}
        </nav>

        <div className="subtitle">Ferramentas de IA</div>

        {error && <div className="error">{error}</div>}

        {isAdmin && (
          <div className="subtitle">
            Para adicionar, editar ou remover ferramentas do catálogo, use a{" "}
            <Link href="/admin/ai-tools">área administrativa</Link>.
          </div>
        )}

        <div className="filter-row">
          <input
            className="input"
            placeholder="Buscar por nome ou descrição..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <input
            className="input"
            placeholder="Categoria (opcional)"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            style={{ maxWidth: 180 }}
          />
        </div>

        {!tools ? (
          <div className="subtitle">Carregando...</div>
        ) : tools.length === 0 ? (
          <div className="empty-state">Nenhuma ferramenta encontrada.</div>
        ) : (
          <div className="tool-grid">
            {tools.map((tool) => (
              <div key={tool.id} className="tool-card">
                <button
                  className={`favorite-btn ${tool.is_favorite ? "favorite-btn--active" : ""}`}
                  onClick={() => handleToggleFavorite(tool.id)}
                  title={tool.is_favorite ? "Remover dos favoritos" : "Adicionar aos favoritos"}
                >
                  {tool.is_favorite ? "★" : "☆"}
                </button>
                <div className="name">{tool.name}</div>
                {tool.description && <div className="desc">{tool.description}</div>}
                {tool.tags.length > 0 && (
                  <div className="tool-tags">
                    {tool.tags.map((tag) => (
                      <span key={tag} className="tag-pill">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
                <a
                  className="btn-secondary"
                  href={tool.url}
                  target="_blank"
                  rel="noreferrer"
                  style={{ display: "block", textAlign: "center", textDecoration: "none" }}
                >
                  Abrir
                </a>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
