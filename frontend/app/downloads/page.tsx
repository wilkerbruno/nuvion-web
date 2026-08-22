"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError, clearTokens, DownloadPublic, getAccessToken } from "@/lib/api";

const STATUS_LABEL: Record<string, string> = {
  in_progress: "Em andamento",
  completed: "Concluído",
  failed: "Falhou",
  cancelled: "Cancelado",
};

export default function DownloadsPage() {
  const router = useRouter();
  const [downloads, setDownloads] = useState<DownloadPublic[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }
    api
      .myDownloads()
      .then(setDownloads)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          clearTokens();
          router.replace("/login");
          return;
        }
        setError(err instanceof ApiError ? err.message : "Erro ao carregar downloads.");
      });
  }, [router]);

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
          <Link href="/notifications">Notificações</Link>
        </nav>

        <div className="subtitle">Downloads</div>

        {error && <div className="error">{error}</div>}

        {!downloads ? (
          <div className="subtitle">Carregando...</div>
        ) : downloads.length === 0 ? (
          <div className="empty-state">
            Nenhum download registrado ainda — o histórico é preenchido pela extensão Nuvion
            quando você baixa um arquivo pelo navegador.
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Arquivo</th>
                  <th>Status</th>
                  <th>Início</th>
                </tr>
              </thead>
              <tbody>
                {downloads.map((d) => (
                  <tr key={d.id}>
                    <td>{d.file_name}</td>
                    <td>
                      <span
                        className={
                          d.status === "completed"
                            ? "badge badge--confirmado"
                            : d.status === "failed" || d.status === "cancelled"
                              ? "badge badge--atrasado"
                              : "badge badge--pendente"
                        }
                      >
                        {(d.status && STATUS_LABEL[d.status]) || d.status || "—"}
                      </span>
                    </td>
                    <td>{d.start_time ? new Date(d.start_time).toLocaleString("pt-BR") : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="foot-link">
          O download em si acontece no seu navegador — a extensão Nuvion só espelha o status aqui.
        </div>
      </div>
    </div>
  );
}
