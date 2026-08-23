"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import QRCode from "qrcode";
import {
  api,
  ApiError,
  PaymentPublic,
  PlanCategory,
  PricesResponse,
  UserPublic,
  clearTokens,
  getAccessToken,
} from "@/lib/api";

// Mercado Pago Card Payment Brick — carregado sob demanda (só quando o
// usuário escolhe "Cartão") via <script> injetado no <head>, sem
// dependência npm: é assim que o próprio Mercado Pago recomenda usar o
// Bricks (SDK client-side, versão pode mudar sem exigir rebuild nosso).
declare global {
  interface Window {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    MercadoPago?: any;
  }
}

const MERCADOPAGO_SDK_URL = "https://sdk.mercadopago.com/js/v2";
let mpSdkPromise: Promise<void> | null = null;

function loadMercadoPagoSdk(): Promise<void> {
  if (typeof window === "undefined") return Promise.reject(new Error("Sem window (SSR)"));
  if (window.MercadoPago) return Promise.resolve();
  if (mpSdkPromise) return mpSdkPromise;

  mpSdkPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = MERCADOPAGO_SDK_URL;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      mpSdkPromise = null;
      reject(new Error("Não foi possível carregar o SDK do Mercado Pago."));
    };
    document.head.appendChild(script);
  });
  return mpSdkPromise;
}

function formatCurrency(amount: number): string {
  return amount.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatUsdt(amount: number): string {
  return `${amount.toFixed(6)} USDT`;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR");
}

function statusBadgeClass(status: string): string {
  return `badge badge--${status.toLowerCase()}`;
}

type PaymentMethod = "pix" | "cartao" | "usdt";

export default function PaymentsPage() {
  const router = useRouter();

  const [user, setUser] = useState<UserPublic | null>(null);
  const [prices, setPrices] = useState<PricesResponse | null>(null);
  const [history, setHistory] = useState<PaymentPublic[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [selectedPlan, setSelectedPlan] = useState<PlanCategory>("Standard");
  const [method, setMethod] = useState<PaymentMethod>("pix");

  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [activePayment, setActivePayment] = useState<PaymentPublic | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);
  const [usdtQrDataUrl, setUsdtQrDataUrl] = useState<string | null>(null);

  const [cardBrickError, setCardBrickError] = useState<string | null>(null);
  const [cardBrickLoading, setCardBrickLoading] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const brickControllerRef = useRef<any>(null);
  const mpPublicKeyRef = useRef<string | null>(null);

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }

    Promise.all([api.me(), api.prices(), api.payments()])
      .then(([meResponse, pricesResponse, paymentsResponse]) => {
        setUser(meResponse);
        setPrices(pricesResponse);
        setHistory(paymentsResponse);
        setSelectedPlan((meResponse.category as PlanCategory) ?? "Standard");
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          clearTokens();
          router.replace("/login");
          return;
        }
        setLoadError(err instanceof ApiError ? err.message : "Erro ao carregar pagamentos.");
      });

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [router]);

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  function startPolling(paymentId: string) {
    stopPolling();
    let attempts = 0;
    pollRef.current = setInterval(async () => {
      attempts += 1;
      try {
        const updated = await api.paymentStatus(paymentId);
        setActivePayment(updated);
        if (updated.status === "Confirmado" || updated.status === "Cancelado") {
          stopPolling();
          api.payments().then(setHistory).catch(() => undefined);
        }
      } catch {
        // erro pontual de rede — tenta de novo no próximo ciclo
      }
      if (attempts >= 75) stopPolling(); // ~5 minutos (75 * 4s)
    }, 4000);
  }

  // Gera o QR Code do pagamento em USDT localmente (sem chamar nenhum
  // serviço externo) sempre que um pagamento USDT ativo muda de carteira.
  useEffect(() => {
    const address = activePayment?.payment_details.wallet_address;
    if (activePayment?.payment_method !== "usdt" || !address) {
      setUsdtQrDataUrl(null);
      return;
    }
    let cancelled = false;
    QRCode.toDataURL(address, { width: 220, margin: 1 })
      .then((url) => {
        if (!cancelled) setUsdtQrDataUrl(url);
      })
      .catch(() => {
        if (!cancelled) setUsdtQrDataUrl(null);
      });
    return () => {
      cancelled = true;
    };
  }, [activePayment]);

  // Monta/desmonta o Card Payment Brick sempre que o método vira "cartao"
  // (ou o plano/valor muda). Só é criado sob demanda — quem nunca clica em
  // "Cartão" nunca carrega o SDK do Mercado Pago nem gasta a chamada de
  // /payments/mercadopago-public-key.
  useEffect(() => {
    if (method !== "cartao" || !prices || !user) {
      if (brickControllerRef.current) {
        brickControllerRef.current.unmount();
        brickControllerRef.current = null;
      }
      return;
    }

    let cancelled = false;
    setCardBrickError(null);
    setCardBrickLoading(true);

    async function mountBrick() {
      try {
        if (!mpPublicKeyRef.current) {
          const { public_key } = await api.mercadopagoPublicKey();
          mpPublicKeyRef.current = public_key;
        }
        await loadMercadoPagoSdk();
        if (cancelled) return;

        if (brickControllerRef.current) {
          brickControllerRef.current.unmount();
          brickControllerRef.current = null;
        }

        const mp = new window.MercadoPago(mpPublicKeyRef.current, { locale: "pt-BR" });
        const controller = await mp.bricks().create("cardPayment", "cardPaymentBrick_container", {
          initialization: {
            amount: prices!.brl[selectedPlan],
            payer: { email: user!.email },
          },
          customization: {
            visual: { style: { theme: "dark" } },
          },
          callbacks: {
            onReady: () => {
              if (!cancelled) setCardBrickLoading(false);
            },
            onError: (error: unknown) => {
              // eslint-disable-next-line no-console
              console.error("Erro no Card Payment Brick:", error);
              if (!cancelled) {
                setCardBrickError("O formulário de cartão encontrou um erro — recarregue a página.");
              }
            },
            onSubmit: ({ formData }: { formData: Record<string, unknown> }) =>
              new Promise<void>((resolve, reject) => {
                (async () => {
                  setCheckoutError(null);
                  setCheckoutLoading(true);
                  setActivePayment(null);
                  stopPolling();
                  try {
                    const payer = (formData.payer ?? {}) as {
                      identification?: { number?: string };
                    };
                    const payment = await api.checkout({
                      method: "cartao",
                      category: selectedPlan,
                      cpf: payer.identification?.number,
                      card_token: formData.token as string,
                      installments: Number(formData.installments) || 1,
                      card_payment_method_id: formData.payment_method_id as string,
                    });
                    setActivePayment(payment);
                    api.payments().then(setHistory).catch(() => undefined);
                    resolve();
                  } catch (err) {
                    setCheckoutError(
                      err instanceof ApiError ? err.message : "Não foi possível processar o cartão."
                    );
                    reject(err);
                  } finally {
                    setCheckoutLoading(false);
                  }
                })();
              }),
          },
        });
        if (cancelled) {
          controller.unmount();
          return;
        }
        brickControllerRef.current = controller;
      } catch (err) {
        if (!cancelled) {
          setCardBrickLoading(false);
          setCardBrickError(
            err instanceof ApiError
              ? err.message
              : "Não foi possível carregar o pagamento por cartão."
          );
        }
      }
    }

    mountBrick();

    return () => {
      cancelled = true;
      if (brickControllerRef.current) {
        brickControllerRef.current.unmount();
        brickControllerRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [method, selectedPlan, prices, user]);

  async function handleCheckout(chosenMethod: "pix" | "usdt") {
    setCheckoutError(null);
    setCheckoutLoading(true);
    setActivePayment(null);
    stopPolling();

    try {
      const payment = await api.checkout({ method: chosenMethod, category: selectedPlan });
      setActivePayment(payment);
      startPolling(payment.id);
    } catch (err) {
      setCheckoutError(err instanceof ApiError ? err.message : "Não foi possível gerar a cobrança.");
    } finally {
      setCheckoutLoading(false);
    }
  }

  async function copyToClipboard(text: string, label: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopyFeedback(`${label} copiado!`);
      setTimeout(() => setCopyFeedback(null), 2500);
    } catch {
      setCopyFeedback("Não foi possível copiar automaticamente — selecione o texto manualmente.");
    }
  }

  if (loadError) {
    return (
      <div className="page">
        <div className="card error">{loadError}</div>
      </div>
    );
  }

  if (!user || !prices) {
    return (
      <div className="page">
        <div className="subtitle">Carregando...</div>
      </div>
    );
  }

  // Ninguém escolhe/muda o plano por aqui, nem Admin — o plano é definido
  // pela área administrativa (fora desta tela) e esta serve só pra
  // pagar/renovar o plano que a conta já tem, no valor correspondente.
  // O plano de checkout fica sempre travado em `user.category`.
  const currentPlan = (user.category as PlanCategory) ?? "Standard";
  const usdtPrice = prices.usdt[selectedPlan];
  const usdtAvailable = usdtPrice !== null && usdtPrice > 0;

  return (
    <div className="page page--top">
      <div className="card card--xwide">
        <div className="topbar">
          <div className="brand">
            Nuvion<span>Web</span>
          </div>
          <Link className="btn-link" href="/dashboard">
            ← Voltar ao painel
          </Link>
        </div>

        <div className="subtitle">
          Plano atual: {user.category} — {user.status}
        </div>

        <div className="section-title">Sua assinatura</div>
        <div className="plan-grid">
          <div className="plan-card plan-card--selected plan-card--readonly">
            <div className="name">{currentPlan}</div>
            <div className="price">{formatCurrency(prices.brl[currentPlan])}</div>
            {prices.usdt[currentPlan] !== null && (
              <div className="price-usdt">≈ {formatUsdt(prices.usdt[currentPlan] as number)}</div>
            )}
          </div>
        </div>
        <div className="subtitle">
          O plano é definido pela área administrativa. Esta tela é só para pagar/renovar sua
          assinatura no valor acima.
        </div>

        <div className="section-title">Forma de pagamento</div>
        <div className="method-toggle">
          <button
            type="button"
            className={`method-btn${method === "pix" ? " method-btn--selected" : ""}`}
            onClick={() => setMethod("pix")}
          >
            PIX
          </button>
          <button
            type="button"
            className={`method-btn${method === "cartao" ? " method-btn--selected" : ""}`}
            onClick={() => setMethod("cartao")}
          >
            Cartão de crédito
          </button>
          <button
            type="button"
            className={`method-btn${method === "usdt" ? " method-btn--selected" : ""}`}
            onClick={() => setMethod("usdt")}
          >
            USDT (cripto)
          </button>
        </div>

        {checkoutError && <div className="error">{checkoutError}</div>}

        {method === "pix" && (
          <button className="btn" type="button" onClick={() => handleCheckout("pix")} disabled={checkoutLoading}>
            {checkoutLoading ? "Gerando cobrança..." : `Gerar cobrança PIX — ${formatCurrency(prices.brl[selectedPlan])}`}
          </button>
        )}

        {method === "usdt" && (
          <>
            {usdtAvailable ? (
              <button
                className="btn"
                type="button"
                onClick={() => handleCheckout("usdt")}
                disabled={checkoutLoading}
              >
                {checkoutLoading
                  ? "Gerando cobrança..."
                  : `Gerar cobrança USDT — ${formatUsdt(usdtPrice as number)}`}
              </button>
            ) : (
              <div className="subtitle">
                Pagamento em USDT ainda não disponível para o plano {selectedPlan}.
              </div>
            )}
          </>
        )}

        {method === "cartao" && (
          <>
            {cardBrickLoading && <div className="subtitle">Carregando formulário de cartão...</div>}
            {cardBrickError && <div className="error">{cardBrickError}</div>}
            <div id="cardPaymentBrick_container" />
          </>
        )}

        {activePayment && (
          <div style={{ marginTop: 20 }}>
            <div className="section-title">Cobrança gerada</div>

            {activePayment.status === "Confirmado" && (
              <div className="success-box">
                Pagamento confirmado! Sua assinatura foi renovada até{" "}
                {formatDate(activePayment.due_date)}.
              </div>
            )}
            {activePayment.status === "Cancelado" && (
              <div className="error">
                Pagamento não foi aprovado
                {activePayment.payment_details.status_detail
                  ? ` (${activePayment.payment_details.status_detail})`
                  : ""}
                . Gere uma nova cobrança.
              </div>
            )}
            {activePayment.status === "Pendente" && (
              <div className="subtitle">Aguardando confirmação do pagamento...</div>
            )}

            {activePayment.payment_method === "pix" && activePayment.payment_details.qr_code_base64 && (
              <>
                <img
                  className="qr-image"
                  src={activePayment.payment_details.qr_code_base64}
                  alt="QR Code do PIX"
                />
                <div className="field">
                  <label className="label">Código copia e cola</label>
                  <div className="mono">{activePayment.payment_details.qr_code}</div>
                </div>
                <button
                  className="btn btn-secondary"
                  type="button"
                  onClick={() =>
                    copyToClipboard(activePayment.payment_details.qr_code || "", "Código PIX")
                  }
                >
                  Copiar código PIX
                </button>
              </>
            )}

            {activePayment.payment_method === "usdt" && (
              <>
                <div className="warning-box">
                  Envie exatamente {activePayment.payment_details.usdt_amount} USDT na rede{" "}
                  {activePayment.payment_details.network} — o valor exato (até a 6ª casa decimal) é
                  o que identifica este pagamento como seu. Um valor diferente pode não ser
                  reconhecido automaticamente.
                </div>
                {usdtQrDataUrl && (
                  <img className="qr-image" src={usdtQrDataUrl} alt="QR Code da carteira USDT" />
                )}
                <div className="field">
                  <label className="label">Endereço da carteira ({activePayment.payment_details.network})</label>
                  <div className="mono">{activePayment.payment_details.wallet_address}</div>
                </div>
                <button
                  className="btn btn-secondary"
                  type="button"
                  onClick={() =>
                    copyToClipboard(activePayment.payment_details.wallet_address || "", "Endereço")
                  }
                >
                  Copiar endereço
                </button>
                <div className="field" style={{ marginTop: 12 }}>
                  <label className="label">Valor exato a enviar</label>
                  <div className="mono">{activePayment.payment_details.usdt_amount} USDT</div>
                </div>
                <button
                  className="btn btn-secondary"
                  type="button"
                  onClick={() =>
                    copyToClipboard(activePayment.payment_details.usdt_amount || "", "Valor")
                  }
                >
                  Copiar valor
                </button>
              </>
            )}

            {copyFeedback && <div className="subtitle" style={{ marginTop: 8 }}>{copyFeedback}</div>}
          </div>
        )}

        <div className="section-title">Histórico de pagamentos</div>
        {history.length === 0 ? (
          <div className="subtitle">Nenhum pagamento ainda.</div>
        ) : (
          <div className="payment-list">
            {history.map((payment) => (
              <div className="payment-row" key={payment.id}>
                <div>
                  <div className="desc">
                    {payment.description} — {payment.payment_method.toUpperCase()}
                  </div>
                  <div className="meta">
                    {payment.payment_method === "usdt" && payment.crypto_amount !== null
                      ? formatUsdt(payment.crypto_amount)
                      : formatCurrency(payment.amount)}{" "}
                    · {formatDate(payment.created_at)}
                  </div>
                </div>
                <span className={statusBadgeClass(payment.status)}>{payment.status}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
