"use client";

import { Fragment, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  AIToolCreatePayload,
  AIToolPublic,
  api,
  ApiError,
  clearTokens,
  CookieSessionSummary,
  DirectCredentialsSummary,
  getAccessToken,
  ProxyPublic,
  UserPublic,
} from "@/lib/api";

const LOGIN_METHODS = [
  { value: "manual", label: "Manual (usuário faz login sozinho)" },
  { value: "credentials", label: "Usuário/senha salvos (autofill)" },
  { value: "cookies", label: "Cookie de sessão salvo" },
];

const PROXY_TYPES = ["HTTP", "HTTPS", "SOCKS4", "SOCKS5"] as const;

type ToolFormState = {
  name: string;
  url: string;
  description: string;
  category: string;
  tags: string;
  observations: string;
  proxy_id: string;
  login_method: string;
  is_featured: boolean;
  block_extensions: boolean;
};

const EMPTY_TOOL_FORM: ToolFormState = {
  name: "",
  url: "",
  description: "",
  category: "",
  tags: "",
  observations: "",
  proxy_id: "",
  login_method: "manual",
  is_featured: false,
  block_extensions: false,
};

type ProxyFormState = {
  name: string;
  host: string;
  port: string;
  proxy_type: (typeof PROXY_TYPES)[number];
  username: string;
  password: string;
};

const EMPTY_PROXY_FORM: ProxyFormState = {
  name: "",
  host: "",
  port: "",
  proxy_type: "HTTP",
  username: "",
  password: "",
};

export default function AdminAIToolsPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserPublic | null>(null);
  const [tools, setTools] = useState<AIToolPublic[] | null>(null);
  const [proxies, setProxies] = useState<ProxyPublic[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [form, setForm] = useState<ToolFormState>(EMPTY_TOOL_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [credSummaries, setCredSummaries] = useState<Record<string, DirectCredentialsSummary>>({});
  const [cookieSummaries, setCookieSummaries] = useState<Record<string, CookieSessionSummary>>({});
  const [credForm, setCredForm] = useState({ username: "", password: "", login_url: "" });
  const [cookiesJson, setCookiesJson] = useState("");
  const [secretsSaving, setSecretsSaving] = useState(false);
  const [secretsError, setSecretsError] = useState<string | null>(null);

  const [proxyForm, setProxyForm] = useState<ProxyFormState>(EMPTY_PROXY_FORM);
  const [proxySaving, setProxySaving] = useState(false);

  function loadTools() {
    api
      .aiTools()
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

  function loadProxies() {
    api.adminProxies().then(setProxies).catch(() => undefined);
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
        loadTools();
        loadProxies();
      })
      .catch(() => router.replace("/login"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  function resetForm() {
    setForm(EMPTY_TOOL_FORM);
    setEditingId(null);
  }

  function startEdit(tool: AIToolPublic) {
    setEditingId(tool.id);
    setForm({
      name: tool.name,
      url: tool.url,
      description: tool.description ?? "",
      category: tool.category ?? "",
      tags: tool.tags.join(", "),
      observations: tool.observations ?? "",
      proxy_id: tool.proxy_id ?? "",
      login_method: tool.login_method,
      is_featured: tool.is_featured,
      block_extensions: tool.block_extensions,
    });
    if (typeof window !== "undefined") window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    const payload: AIToolCreatePayload = {
      name: form.name,
      url: form.url,
      description: form.description || undefined,
      category: form.category || undefined,
      tags: form.tags
        ? form.tags
            .split(",")
            .map((t) => t.trim())
            .filter(Boolean)
        : [],
      observations: form.observations || undefined,
      proxy_id: form.proxy_id || undefined,
      login_method: form.login_method,
      is_featured: form.is_featured,
      block_extensions: form.block_extensions,
    };
    try {
      if (editingId) {
        await api.updateAITool(editingId, payload);
        setNotice("Ferramenta atualizada.");
      } else {
        await api.createAITool(payload);
        setNotice("Ferramenta criada.");
      }
      resetForm();
      loadTools();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao salvar ferramenta.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(toolId: string) {
    try {
      await api.deleteAITool(toolId);
      if (editingId === toolId) resetForm();
      if (expandedId === toolId) setExpandedId(null);
      loadTools();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao remover ferramenta.");
    }
  }

  async function toggleExpand(tool: AIToolPublic) {
    if (expandedId === tool.id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(tool.id);
    setSecretsError(null);
    setCredForm({ username: "", password: "", login_url: "" });
    setCookiesJson("");
    try {
      const [cred, cookies] = await Promise.all([
        api.aiToolCredentials(tool.id),
        api.aiToolCookies(tool.id),
      ]);
      setCredSummaries((s) => ({ ...s, [tool.id]: cred }));
      setCookieSummaries((s) => ({ ...s, [tool.id]: cookies }));
    } catch (err) {
      setSecretsError(
        err instanceof ApiError ? err.message : "Erro ao carregar login da ferramenta."
      );
    }
  }

  async function handleSetCredentials(toolId: string) {
    setSecretsSaving(true);
    setSecretsError(null);
    try {
      const summary = await api.setAIToolCredentials(toolId, {
        username: credForm.username,
        password: credForm.password,
        login_url: credForm.login_url || undefined,
      });
      setCredSummaries((s) => ({ ...s, [toolId]: summary }));
      setCredForm({ username: "", password: "", login_url: "" });
      setNotice("Credenciais salvas.");
    } catch (err) {
      setSecretsError(err instanceof ApiError ? err.message : "Erro ao salvar credenciais.");
    } finally {
      setSecretsSaving(false);
    }
  }

  async function handleDeleteCredentials(toolId: string) {
    setSecretsSaving(true);
    setSecretsError(null);
    try {
      await api.deleteAIToolCredentials(toolId);
      setCredSummaries((s) => ({ ...s, [toolId]: { configured: false } }));
    } catch (err) {
      setSecretsError(err instanceof ApiError ? err.message : "Erro ao remover credenciais.");
    } finally {
      setSecretsSaving(false);
    }
  }

  async function handleSetCookies(toolId: string) {
    setSecretsSaving(true);
    setSecretsError(null);
    try {
      let parsed: unknown;
      try {
        parsed = JSON.parse(cookiesJson);
      } catch {
        throw new Error("JSON de cookies inválido — confira a formatação.");
      }
      if (!Array.isArray(parsed)) {
        throw new Error('Cole uma lista JSON de cookies, ex.: [{"name":"...","value":"..."}]');
      }
      const summary = await api.setAIToolCookies(toolId, parsed as Record<string, unknown>[]);
      setCookieSummaries((s) => ({ ...s, [toolId]: summary }));
      setCookiesJson("");
      setNotice("Cookies salvos.");
    } catch (err) {
      setSecretsError(
        err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Erro ao salvar cookies."
      );
    } finally {
      setSecretsSaving(false);
    }
  }

  async function handleDeleteCookies(toolId: string) {
    setSecretsSaving(true);
    setSecretsError(null);
    try {
      await api.deleteAIToolCookies(toolId);
      setCookieSummaries((s) => ({ ...s, [toolId]: { configured: false } }));
    } catch (err) {
      setSecretsError(err instanceof ApiError ? err.message : "Erro ao remover cookies.");
    } finally {
      setSecretsSaving(false);
    }
  }

  async function handleCreateProxy(event: React.FormEvent) {
    event.preventDefault();
    setProxySaving(true);
    setError(null);
    try {
      await api.createAdminProxy({
        name: proxyForm.name,
        host: proxyForm.host,
        port: Number(proxyForm.port),
        proxy_type: proxyForm.proxy_type,
        username: proxyForm.username || undefined,
        password: proxyForm.password || undefined,
      });
      setProxyForm(EMPTY_PROXY_FORM);
      setNotice("Proxy criado.");
      loadProxies();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao criar proxy.");
    } finally {
      setProxySaving(false);
    }
  }

  async function handleDeleteProxy(proxyId: string) {
    try {
      await api.deleteAdminProxy(proxyId);
      loadProxies();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao remover proxy — confira se nenhuma ferramenta ainda o usa.");
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

        <div className="subtitle">Ferramentas de IA — administração</div>

        {error && <div className="error">{error}</div>}
        {notice && <div className="success-box">{notice}</div>}

        <div className="section-title">{editingId ? "Editar ferramenta" : "Nova ferramenta"}</div>
        <form className="inline-form" onSubmit={handleSubmit}>
          <input
            className="input"
            placeholder="Nome"
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <input
            className="input"
            placeholder="URL"
            required
            value={form.url}
            onChange={(e) => setForm({ ...form, url: e.target.value })}
          />
          <input
            className="input"
            placeholder="Categoria"
            value={form.category}
            onChange={(e) => setForm({ ...form, category: e.target.value })}
          />
          <input
            className="input"
            placeholder="Descrição"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
          <input
            className="input"
            placeholder="Tags (separadas por vírgula)"
            value={form.tags}
            onChange={(e) => setForm({ ...form, tags: e.target.value })}
          />
          <input
            className="input"
            placeholder="Observações (uso interno, não aparece pro usuário)"
            value={form.observations}
            onChange={(e) => setForm({ ...form, observations: e.target.value })}
          />

          <div className="field">
            <label className="label">Proxy atribuído (opcional)</label>
            <select
              className="input"
              value={form.proxy_id}
              onChange={(e) => setForm({ ...form, proxy_id: e.target.value })}
            >
              <option value="">Sem proxy</option>
              {proxies.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.host}:{p.port})
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label className="label">Método de login</label>
            <select
              className="input"
              value={form.login_method}
              onChange={(e) => setForm({ ...form, login_method: e.target.value })}
            >
              {LOGIN_METHODS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>

          <label className="subtitle" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input
              type="checkbox"
              checked={form.is_featured}
              onChange={(e) => setForm({ ...form, is_featured: e.target.checked })}
            />
            Destacar no catálogo
          </label>
          <label className="subtitle" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input
              type="checkbox"
              checked={form.block_extensions}
              onChange={(e) => setForm({ ...form, block_extensions: e.target.checked })}
            />
            Bloquear outras extensões ao abrir esta ferramenta
          </label>

          <div style={{ display: "flex", gap: 10 }}>
            <button className="btn" type="submit" disabled={saving}>
              {saving ? "Salvando..." : editingId ? "Salvar alterações" : "Criar ferramenta"}
            </button>
            {editingId && (
              <button className="btn-secondary" type="button" onClick={resetForm}>
                Cancelar edição
              </button>
            )}
          </div>
        </form>

        <div className="section-title">Catálogo ({tools?.length ?? 0})</div>
        {!tools ? (
          <div className="subtitle">Carregando...</div>
        ) : tools.length === 0 ? (
          <div className="empty-state">Nenhuma ferramenta cadastrada ainda.</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Categoria</th>
                  <th>Proxy</th>
                  <th>Login</th>
                  <th>Destacada</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody>
                {tools.map((tool) => {
                  const proxy = proxies.find((p) => p.id === tool.proxy_id);
                  return (
                    <Fragment key={tool.id}>
                      <tr>
                        <td>{tool.name}</td>
                        <td>{tool.category || "—"}</td>
                        <td>{proxy ? proxy.name : "—"}</td>
                        <td>
                          {LOGIN_METHODS.find((m) => m.value === tool.login_method)?.label ??
                            tool.login_method}
                        </td>
                        <td>{tool.is_featured ? "Sim" : "Não"}</td>
                        <td style={{ whiteSpace: "nowrap" }}>
                          <button className="btn-link" onClick={() => startEdit(tool)}>
                            Editar
                          </button>{" "}
                          <button className="btn-link" onClick={() => toggleExpand(tool)}>
                            {expandedId === tool.id ? "Fechar login" : "Login"}
                          </button>{" "}
                          <button
                            className="btn-link"
                            style={{ color: "var(--danger)" }}
                            onClick={() => handleDelete(tool.id)}
                          >
                            Remover
                          </button>
                        </td>
                      </tr>
                      {expandedId === tool.id && (
                        <tr>
                          <td colSpan={6}>
                            <div style={{ display: "flex", flexDirection: "column", gap: 16, padding: "12px 0" }}>
                              {secretsError && <div className="error">{secretsError}</div>}

                              <div>
                                <div className="label">
                                  Credenciais diretas (usuário/senha) —{" "}
                                  {credSummaries[tool.id]?.configured ? "configuradas" : "não configuradas"}
                                </div>
                                {credSummaries[tool.id]?.configured && (
                                  <div className="subtitle">
                                    Usuário atual: {credSummaries[tool.id]?.username ?? "—"}
                                  </div>
                                )}
                                <div className="inline-form" style={{ marginTop: 8 }}>
                                  <input
                                    className="input"
                                    placeholder="Usuário"
                                    value={credForm.username}
                                    onChange={(e) => setCredForm({ ...credForm, username: e.target.value })}
                                  />
                                  <input
                                    className="input"
                                    placeholder="Senha"
                                    type="password"
                                    value={credForm.password}
                                    onChange={(e) => setCredForm({ ...credForm, password: e.target.value })}
                                  />
                                  <input
                                    className="input"
                                    placeholder="URL de login (opcional)"
                                    value={credForm.login_url}
                                    onChange={(e) => setCredForm({ ...credForm, login_url: e.target.value })}
                                  />
                                  <div style={{ display: "flex", gap: 10 }}>
                                    <button
                                      className="btn-secondary"
                                      type="button"
                                      disabled={secretsSaving || !credForm.username || !credForm.password}
                                      onClick={() => handleSetCredentials(tool.id)}
                                    >
                                      Salvar credenciais
                                    </button>
                                    {credSummaries[tool.id]?.configured && (
                                      <button
                                        className="btn-link"
                                        style={{ color: "var(--danger)" }}
                                        type="button"
                                        onClick={() => handleDeleteCredentials(tool.id)}
                                      >
                                        Remover credenciais
                                      </button>
                                    )}
                                  </div>
                                </div>
                              </div>

                              <div>
                                <div className="label">
                                  Cookie de sessão —{" "}
                                  {cookieSummaries[tool.id]?.configured
                                    ? `configurado (${cookieSummaries[tool.id]?.cookies_count ?? 0} cookies, domínio ${
                                        cookieSummaries[tool.id]?.domain ?? "—"
                                      })`
                                    : "não configurado"}
                                </div>
                                <textarea
                                  className="input"
                                  rows={3}
                                  placeholder='Cole a lista de cookies em JSON, ex.: [{"name":"session_id","value":"...","domain":".exemplo.com"}]'
                                  value={cookiesJson}
                                  onChange={(e) => setCookiesJson(e.target.value)}
                                  style={{ width: "100%", fontFamily: "monospace", marginTop: 8 }}
                                />
                                <div style={{ display: "flex", gap: 10, marginTop: 8 }}>
                                  <button
                                    className="btn-secondary"
                                    type="button"
                                    disabled={secretsSaving || !cookiesJson.trim()}
                                    onClick={() => handleSetCookies(tool.id)}
                                  >
                                    Salvar cookies
                                  </button>
                                  {cookieSummaries[tool.id]?.configured && (
                                    <button
                                      className="btn-link"
                                      style={{ color: "var(--danger)" }}
                                      type="button"
                                      onClick={() => handleDeleteCookies(tool.id)}
                                    >
                                      Remover cookies
                                    </button>
                                  )}
                                </div>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="section-title">Proxies globais (atribuíveis a ferramentas)</div>
        <div className="subtitle">
          Diferente dos proxies pessoais que cada usuário cadastra na extensão — estes são
          escolhidos pelo admin e vinculados a uma ferramenta específica (campo &quot;Proxy
          atribuído&quot; acima).
        </div>
        <form className="inline-form" onSubmit={handleCreateProxy}>
          <input
            className="input"
            placeholder="Nome"
            required
            value={proxyForm.name}
            onChange={(e) => setProxyForm({ ...proxyForm, name: e.target.value })}
          />
          <input
            className="input"
            placeholder="Host"
            required
            value={proxyForm.host}
            onChange={(e) => setProxyForm({ ...proxyForm, host: e.target.value })}
          />
          <input
            className="input"
            placeholder="Porta"
            required
            type="number"
            value={proxyForm.port}
            onChange={(e) => setProxyForm({ ...proxyForm, port: e.target.value })}
          />
          <select
            className="input"
            value={proxyForm.proxy_type}
            onChange={(e) => setProxyForm({ ...proxyForm, proxy_type: e.target.value as ProxyFormState["proxy_type"] })}
          >
            {PROXY_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <input
            className="input"
            placeholder="Usuário (opcional)"
            value={proxyForm.username}
            onChange={(e) => setProxyForm({ ...proxyForm, username: e.target.value })}
          />
          <input
            className="input"
            placeholder="Senha (opcional)"
            type="password"
            value={proxyForm.password}
            onChange={(e) => setProxyForm({ ...proxyForm, password: e.target.value })}
          />
          <button className="btn" type="submit" disabled={proxySaving}>
            {proxySaving ? "Salvando..." : "Adicionar proxy"}
          </button>
        </form>

        {proxies.length === 0 ? (
          <div className="empty-state">Nenhum proxy global cadastrado ainda.</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Host</th>
                  <th>Porta</th>
                  <th>Tipo</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody>
                {proxies.map((p) => (
                  <tr key={p.id}>
                    <td>{p.name}</td>
                    <td>{p.host}</td>
                    <td>{p.port}</td>
                    <td>{p.proxy_type}</td>
                    <td>
                      <button
                        className="btn-link"
                        style={{ color: "var(--danger)" }}
                        onClick={() => handleDeleteProxy(p.id)}
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
