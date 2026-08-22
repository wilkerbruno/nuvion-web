"use client";

import { FormEvent, Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, ApiError, RegisterPayload } from "@/lib/api";

const emptyForm: RegisterPayload = {
  username: "",
  email: "",
  password: "",
  name: "",
  phone: "",
  cpf: "",
  referral_code: "",
};

// useSearchParams() (para pré-preencher o código de indicação a partir de um
// link tipo /register?ref=ABC123) exige um limite de Suspense no App Router,
// senão o Next falha ao pré-renderizar a página estaticamente.
export default function RegisterPage() {
  return (
    <Suspense fallback={null}>
      <RegisterForm />
    </Suspense>
  );
}

function RegisterForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [form, setForm] = useState<RegisterPayload>({
    ...emptyForm,
    referral_code: searchParams.get("ref") ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function update<K extends keyof RegisterPayload>(key: K, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.register({ ...form, cpf: form.cpf?.trim() ? form.cpf : undefined });
      router.push("/login");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível criar a conta.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page page--top">
      <form className="card card--wide" onSubmit={handleSubmit}>
        <div className="brand">
          Nuvion<span>Web</span>
        </div>
        <div className="subtitle">
          Criar conta — é necessário um código de indicação de um usuário existente.
        </div>

        {error && <div className="error">{error}</div>}

        <div className="field">
          <label className="label" htmlFor="name">
            Nome completo
          </label>
          <input
            id="name"
            className="input"
            value={form.name}
            onChange={(e) => update("name", e.target.value)}
            required
          />
        </div>

        <div className="field">
          <label className="label" htmlFor="username">
            Usuário
          </label>
          <input
            id="username"
            className="input"
            value={form.username}
            onChange={(e) => update("username", e.target.value)}
            minLength={3}
            required
          />
        </div>

        <div className="field">
          <label className="label" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            className="input"
            type="email"
            value={form.email}
            onChange={(e) => update("email", e.target.value)}
            required
          />
        </div>

        <div className="field">
          <label className="label" htmlFor="phone">
            Telefone (com DDD)
          </label>
          <input
            id="phone"
            className="input"
            value={form.phone}
            onChange={(e) => update("phone", e.target.value)}
            placeholder="11999998888"
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
            value={form.password}
            onChange={(e) => update("password", e.target.value)}
            minLength={8}
            required
          />
        </div>

        <div className="field">
          <label className="label" htmlFor="referral_code">
            Código de indicação
          </label>
          <input
            id="referral_code"
            className="input"
            value={form.referral_code}
            onChange={(e) => update("referral_code", e.target.value)}
            required
          />
        </div>

        <button className="btn" type="submit" disabled={loading}>
          {loading ? "Criando conta..." : "Criar conta"}
        </button>

        <div className="foot-link">
          Já tem conta? <Link href="/login">Entrar</Link>
        </div>
      </form>
    </div>
  );
}
