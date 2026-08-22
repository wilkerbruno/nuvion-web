"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError, saveTokens } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [usernameOrEmail, setUsernameOrEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const tokens = await api.login(usernameOrEmail, password);
      saveTokens(tokens.access_token, tokens.refresh_token);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível entrar. Tente novamente.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <form className="card" onSubmit={handleSubmit}>
        <div className="brand">
          Nuvion<span>Web</span>
        </div>
        <div className="subtitle">Entre com seu usuário ou email.</div>

        {error && <div className="error">{error}</div>}

        <div className="field">
          <label className="label" htmlFor="usernameOrEmail">
            Usuário ou email
          </label>
          <input
            id="usernameOrEmail"
            className="input"
            value={usernameOrEmail}
            onChange={(e) => setUsernameOrEmail(e.target.value)}
            autoComplete="username"
            required
          />
        </div>

        <div className="field">
          <label className="label" htmlFor="password">
            Senha
          </label>
          <input
            id="password"
            className="input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>

        <button className="btn" type="submit" disabled={loading}>
          {loading ? "Entrando..." : "Entrar"}
        </button>

        <div className="foot-link">
          Ainda não tem conta? <Link href="/register">Criar conta</Link>
        </div>
      </form>
    </div>
  );
}
