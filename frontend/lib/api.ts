// Cliente HTTP mínimo para a API do Nuvion Web (backend/app/main.py).
// Sem dependência externa (axios etc.) — só fetch nativo, guardando os
// tokens em localStorage no navegador do usuário (equivalente web da
// sessão local que o app desktop guardava em disco).

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const ACCESS_TOKEN_KEY = "nuvion_access_token";
const REFRESH_TOKEN_KEY = "nuvion_refresh_token";

export function saveTokens(accessToken: string, refreshToken: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  window.localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function clearTokens() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { auth?: boolean } = {}
): Promise<T> {
  const { auth = false, headers, ...rest } = options;

  const finalHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...(headers as Record<string, string> | undefined),
  };

  if (auth) {
    const token = getAccessToken();
    if (token) finalHeaders["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}${path}`, { ...rest, headers: finalHeaders });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      // corpo não era JSON — mantém statusText
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// --- Tipos espelhando app/schemas/*.py ---

export interface UserPublic {
  id: string;
  username: string;
  email: string;
  name: string;
  phone: string;
  cpf: string | null;
  avatar_url: string | null;
  referral_code: string;
  account_type: string;
  status: string;
  category: string;
  last_login: string | null;
  payment_due_date: string | null;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface DashboardSummary {
  user: UserPublic;
  payment_status: {
    has_due_date: boolean;
    status: string;
    is_overdue: boolean;
    days_remaining: number | null;
    formatted_date?: string;
  };
  is_blocked: boolean;
  block_message: string | null;
}

export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
  name: string;
  phone: string;
  cpf?: string;
  referral_code: string;
}

export type PlanCategory = "Standard" | "Premium" | "VIP";

export interface CheckoutPayload {
  method: "pix" | "cartao" | "usdt";
  category?: PlanCategory;
  cpf?: string;
  // Só para "cartao" — gerados no navegador pelo Mercado Pago Card Payment
  // Brick (o backend nunca vê o número do cartão, só o token).
  card_token?: string;
  installments?: number;
  card_payment_method_id?: string;
}

export interface PaymentPublic {
  id: string;
  amount: number;
  // Valor exato em USDT (6 casas) — só presente para pagamentos "usdt".
  crypto_amount: number | null;
  payment_method: string;
  description: string;
  status: string;
  due_date: string;
  payment_date: string | null;
  payment_details: {
    qr_code?: string;
    qr_code_base64?: string;
    date_of_expiration?: string;
    // Cartão (Mercado Pago)
    status_detail?: string;
    payment_method_id?: string;
    installments?: number;
    // USDT (TRC20)
    wallet_address?: string;
    network?: string;
    usdt_amount?: string;
    [key: string]: unknown;
  };
  transaction_id: string | null;
  created_at: string;
}

export type PlanPrices = Record<PlanCategory, number>;

export interface PricesResponse {
  brl: PlanPrices;
  // null para uma categoria que o admin ainda não configurou preço em USDT
  // — nesse caso o checkout em USDT não fica disponível pra ela.
  usdt: Record<PlanCategory, number | null>;
}

export interface MercadoPagoPublicKey {
  public_key: string;
}

// --- Tipos Fase 4 (diamantes, IA, notificações, downloads) ---

export interface RewardTransaction {
  id: string;
  type: string;
  diamonds: number;
  balance_after: number;
  description: string;
  timestamp: string;
  reference_id?: string | null;
}

export interface RewardBalance {
  diamonds: number;
  diamond_rate: number;
  transactions: RewardTransaction[];
  claimed_rewards: string[];
  referral_code: string;
  referral_reward: number;
}

export interface RewardCatalogItem {
  id: string;
  icon: string;
  title: string;
  description: string;
  points: number;
  available: boolean;
  already_claimed: boolean;
}

export interface ClaimRewardResponse {
  success: boolean;
  message: string;
  diamonds: number;
}

export interface AIToolPublic {
  id: string;
  name: string;
  url: string;
  description: string | null;
  category: string | null;
  tags: string[];
  observations: string | null;
  proxy_id: string | null;
  block_extensions: boolean;
  is_featured: boolean;
  login_method: string;
  is_favorite: boolean;
}

export interface AIToolCreatePayload {
  name: string;
  url: string;
  description?: string;
  category?: string;
  tags?: string[];
  observations?: string;
  proxy_id?: string;
  login_method?: string;
  is_featured?: boolean;
  block_extensions?: boolean;
}

// Todos os campos opcionais — só o que for enviado é alterado
// (backend usa `exclude_unset=True`, ver AIToolUpdate em app/schemas/ai_tool.py).
export type AIToolUpdatePayload = Partial<AIToolCreatePayload>;

export interface FavoriteToggleResponse {
  ai_tool_id: string;
  is_favorite: boolean;
}

// --- Proxies (pessoais em /proxies, globais/admin em /admin/proxies) ---

export interface ProxyPublic {
  id: string;
  name: string;
  host: string;
  port: number;
  proxy_type: string;
  username: string | null;
  password: string | null;
  is_active: boolean;
  is_selected: boolean;
  status: string;
  response_time: number | null;
}

export interface ProxyCreatePayload {
  name: string;
  host: string;
  port: number;
  proxy_type: "HTTP" | "HTTPS" | "SOCKS4" | "SOCKS5";
  username?: string;
  password?: string;
}

export type ProxyUpdatePayload = Partial<ProxyCreatePayload> & { is_active?: boolean };

// --- Recompensas — admin (/admin/rewards) ---

export interface RewardAdminItem {
  id: string;
  icon: string;
  title: string;
  description: string;
  points: number;
  available: boolean;
}

export interface RewardCreatePayload {
  icon?: string;
  title: string;
  description?: string;
  points: number;
  available?: boolean;
}

export type RewardUpdatePayload = Partial<RewardCreatePayload>;

// --- Credenciais diretas / cookies por ferramenta de IA (admin escreve,
// qualquer usuário autenticado lê só o resumo — nunca o segredo) ---

export interface DirectCredentialsSummary {
  configured: boolean;
  username?: string | null;
  login_url?: string | null;
  is_active?: boolean | null;
  login_status?: string | null;
  failed_attempts?: number | null;
  max_attempts?: number | null;
}

export interface DirectCredentialsSetPayload {
  username: string;
  password: string;
  login_url?: string;
  username_selector?: string;
  password_selector?: string;
  submit_selector?: string;
}

// --- Administração de usuários (definir plano, bloquear/desbloquear) ---

export type UserStatus = "Ativo" | "Inativo" | "Cancelado" | "Bloqueado";

export interface AdminUserUpdatePayload {
  category?: PlanCategory;
  status?: UserStatus;
}

export interface CookieSessionSummary {
  configured: boolean;
  id?: string | null;
  domain?: string | null;
  cookies_count?: number | null;
  status?: string | null;
  is_active?: boolean | null;
  is_enabled?: boolean | null;
  expires_at?: string | null;
  created_at?: string | null;
  source_file?: string | null;
}

export interface NotificationPublic {
  id: string;
  user_id: string | null;
  is_global: boolean;
  type: string;
  priority: string;
  title: string;
  message: string;
  icon: string;
  extra_data: Record<string, unknown>;
  is_read: boolean;
  expires_at: string | null;
  created_at: string;
}

export interface UnreadCount {
  unread_count: number;
}

export interface DownloadPublic {
  id: string;
  file_name: string;
  file_path: string | null;
  url: string | null;
  start_time: string | null;
  end_time: string | null;
  status: string | null;
  created_at: string;
}

// --- Endpoints ---

export const api = {
  login: (usernameOrEmail: string, password: string) =>
    request<TokenPair>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username_or_email: usernameOrEmail, password }),
    }),

  register: (payload: RegisterPayload) =>
    request<UserPublic>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  me: () => request<UserPublic>("/auth/me", { auth: true }),

  dashboard: () => request<DashboardSummary>("/dashboard/me", { auth: true }),

  prices: () => request<PricesResponse>("/payments/prices", { auth: true }),

  mercadopagoPublicKey: () =>
    request<MercadoPagoPublicKey>("/payments/mercadopago-public-key", { auth: true }),

  payments: () => request<PaymentPublic[]>("/payments/me", { auth: true }),

  checkout: (payload: CheckoutPayload) =>
    request<PaymentPublic>("/payments/checkout", {
      method: "POST",
      auth: true,
      body: JSON.stringify(payload),
    }),

  paymentStatus: (id: string) => request<PaymentPublic>(`/payments/${id}`, { auth: true }),

  // --- Diamantes / recompensas ---
  myRewards: () => request<RewardBalance>("/rewards/me", { auth: true }),

  rewardsCatalog: () => request<RewardCatalogItem[]>("/rewards/catalog", { auth: true }),

  claimReward: (rewardId: string) =>
    request<ClaimRewardResponse>(`/rewards/claim/${rewardId}`, { method: "POST", auth: true }),

  // --- Ferramentas de IA / favoritos ---
  aiTools: (params?: { category?: string; search?: string }) => {
    const qs = new URLSearchParams();
    if (params?.category) qs.set("category", params.category);
    if (params?.search) qs.set("search", params.search);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<AIToolPublic[]>(`/ai-tools${suffix}`, { auth: true });
  },

  favoriteTools: () => request<AIToolPublic[]>("/ai-tools/favorites", { auth: true }),

  createAITool: (payload: AIToolCreatePayload) =>
    request<AIToolPublic>("/ai-tools", { method: "POST", auth: true, body: JSON.stringify(payload) }),

  updateAITool: (toolId: string, payload: AIToolUpdatePayload) =>
    request<AIToolPublic>(`/ai-tools/${toolId}`, {
      method: "PATCH",
      auth: true,
      body: JSON.stringify(payload),
    }),

  deleteAITool: (toolId: string) =>
    request<void>(`/ai-tools/${toolId}`, { method: "DELETE", auth: true }),

  toggleFavorite: (toolId: string) =>
    request<FavoriteToggleResponse>(`/ai-tools/${toolId}/favorite`, { method: "POST", auth: true }),

  // --- Credenciais/cookies por ferramenta (leitura: qualquer usuário; escrita: admin) ---
  aiToolCredentials: (toolId: string) =>
    request<DirectCredentialsSummary>(`/ai-tools/${toolId}/credentials`, { auth: true }),

  setAIToolCredentials: (toolId: string, payload: DirectCredentialsSetPayload) =>
    request<DirectCredentialsSummary>(`/ai-tools/${toolId}/credentials`, {
      method: "PUT",
      auth: true,
      body: JSON.stringify(payload),
    }),

  deleteAIToolCredentials: (toolId: string) =>
    request<void>(`/ai-tools/${toolId}/credentials`, { method: "DELETE", auth: true }),

  aiToolCookies: (toolId: string) =>
    request<CookieSessionSummary>(`/ai-tools/${toolId}/cookies`, { auth: true }),

  setAIToolCookies: (toolId: string, cookiesData: Record<string, unknown>[]) =>
    request<CookieSessionSummary>(`/ai-tools/${toolId}/cookies`, {
      method: "PUT",
      auth: true,
      body: JSON.stringify({ cookies_data: cookiesData }),
    }),

  deleteAIToolCookies: (toolId: string) =>
    request<void>(`/ai-tools/${toolId}/cookies`, { method: "DELETE", auth: true }),

  // --- Proxies globais/admin (atribuíveis a uma ferramenta via proxy_id) ---
  adminProxies: () => request<ProxyPublic[]>("/admin/proxies", { auth: true }),

  createAdminProxy: (payload: ProxyCreatePayload) =>
    request<ProxyPublic>("/admin/proxies", { method: "POST", auth: true, body: JSON.stringify(payload) }),

  updateAdminProxy: (proxyId: string, payload: ProxyUpdatePayload) =>
    request<ProxyPublic>(`/admin/proxies/${proxyId}`, {
      method: "PATCH",
      auth: true,
      body: JSON.stringify(payload),
    }),

  deleteAdminProxy: (proxyId: string) =>
    request<void>(`/admin/proxies/${proxyId}`, { method: "DELETE", auth: true }),

  // --- Recompensas — admin ---
  adminRewards: () => request<RewardAdminItem[]>("/admin/rewards", { auth: true }),

  createReward: (payload: RewardCreatePayload) =>
    request<RewardAdminItem>("/admin/rewards", { method: "POST", auth: true, body: JSON.stringify(payload) }),

  updateReward: (rewardId: string, payload: RewardUpdatePayload) =>
    request<RewardAdminItem>(`/admin/rewards/${rewardId}`, {
      method: "PATCH",
      auth: true,
      body: JSON.stringify(payload),
    }),

  deleteReward: (rewardId: string) =>
    request<void>(`/admin/rewards/${rewardId}`, { method: "DELETE", auth: true }),

  // --- Usuários — admin (definir plano, bloquear/desbloquear) ---
  adminUsers: (search?: string) =>
    request<UserPublic[]>(`/admin/users${search ? `?search=${encodeURIComponent(search)}` : ""}`, {
      auth: true,
    }),

  adminUser: (userId: string) => request<UserPublic>(`/admin/users/${userId}`, { auth: true }),

  updateAdminUser: (userId: string, payload: AdminUserUpdatePayload) =>
    request<UserPublic>(`/admin/users/${userId}`, {
      method: "PATCH",
      auth: true,
      body: JSON.stringify(payload),
    }),

  // --- Notificações ---
  myNotifications: (includeRead = false) =>
    request<NotificationPublic[]>(`/notifications/me?include_read=${includeRead}`, { auth: true }),

  unreadNotificationCount: () => request<UnreadCount>("/notifications/me/unread-count", { auth: true }),

  markNotificationRead: (id: string) =>
    request<NotificationPublic>(`/notifications/${id}/read`, { method: "POST", auth: true }),

  markAllNotificationsRead: () =>
    request<{ marked_count: number }>("/notifications/me/read-all", { method: "POST", auth: true }),

  deleteNotification: (id: string) =>
    request<void>(`/notifications/${id}`, { method: "DELETE", auth: true }),

  // --- Downloads ---
  myDownloads: () => request<DownloadPublic[]>("/downloads/me", { auth: true }),
};
