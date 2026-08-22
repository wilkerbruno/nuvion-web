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
  const [notice, setNotice] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newTool, setNewTool] = useState({ name: "", url: "", category: "", description: "" });
  const [saving, setSaving] = useState(false);

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

  async function handleCreateTool(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.createAITool({
        name: newTool.name,
        url: newTool.url,
        category: newTool.category || undefined,
        description: newTool.description || undefined,
      });
      setNewTool({ name: "", url: "", category: "", description: "" });
      setShowAddForm(false);
      setNotice("Ferramenta adicionada ao catálogo.");
      loadTools();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao criar ferramenta.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteTool(toolId: string) {
    try {
      await api.deleteAITool(toolId);
      loadTools();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao remover ferramenta.");
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
        </nav>

        <div className="subtitle">Ferramentas de IA</div>

        {error && <div className="error">{error}</div>}
        {notice && <div className="success-box">{notice}</div>}

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

        {isAdmin && (
          <>
            <button className="btn-secondary" onClick={() => setShowAddForm((v) => !v)}>
              {showAddForm ? "Cancelar" : "+ Adicionar ferramenta ao catálogo"}
            </button>

            {showAddForm && (
              <form className="inline-form" onSubmit={handleCreateTool}>
                <input
                  className="input"
                  placeholder="Nome"
                  required
                  value={newTool.name}
                  onChange={(e) => setNewTool({ ...newTool, name: e.target.value })}
                />
                <input
                  className="input"
                  placeholder="URL"
                  required
                  value={newTool.url}
                  onChange={(e) => setNewTool({ ...newTool, url: e.target.value })}
                />
                <input
                  className="input"
                  placeholder="Categoria"
                  value={newTool.category}
                  onChange={(e) => setNewTool({ ...newTool, category: e.target.value })}
                />
                <input
                  className="input"
                  placeholder="Descrição"
                  value={newTool.description}
                  onChange={(e) => setNewTool({ ...newTool, description: e.target.value })}
                />
                <button className="btn" type="submit" disabled={saving}>
                  {saving ? "Salvando..." : "Salvar"}
                </button>
              </form>
            )}
          </>
        )}

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
                {isAdmin && (
                  <button
                    className="btn-link"
                    style={{ marginTop: 8, color: "var(--danger)" }}
                    onClick={() => handleDeleteTool(tool.id)}
                  >
                    Remover do catálogo
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        <div className="foot-link">
          Credenciais diretas e cookies de sessão por ferramenta ficam disponíveis via API
          (/ai-tools/&#123;id&#125;/credentials, /cookies) — a UI de administração deles chega numa
          próxima iteração; login automático de verdade ainda não existe na versão web (ver
          backend/README.md).
        </div>
      </div>
    </div>
  );
}
