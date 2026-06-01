// frontend/src/components/pages/PanelPage.jsx
import { useEffect, useState, useCallback } from "react";
import { useToolsStore, useAuthStore } from "../../stores";
import toast from "react-hot-toast";
import {
  LayoutGrid, List, Search, Heart, Trash2, ExternalLink,
  Loader2, Plus,
} from "lucide-react";
import clsx from "clsx";

const CATEGORIES = [
  { id: "todas",       label: "Todas as Ferramentas" },
  { id: "conversacao", label: "Conversação" },
  { id: "imagem",      label: "Imagem" },
  { id: "codigo",      label: "Programação" },
  { id: "escrita",     label: "Escrita" },
  { id: "analise",     label: "Análise" },
  { id: "favoritos",   label: "⭐ Favoritos" },
];

const CATEGORY_COLORS = {
  conversacao: "#4F46E5",
  imagem:      "#0284C7",
  codigo:      "#B45309",
  escrita:     "#047857",
  video:       "#B91C1C",
  audio:       "#9D174D",
  analise:     "#0E7490",
};

// ── ToolCard ──────────────────────────────────────────────────────────────────
function ToolCard({ tool, onOpen, onFavorite, onDelete, isAdmin }) {
  const [opening, setOpening] = useState(false);
  const color = CATEGORY_COLORS[tool.category] || "#334155";
  const urlClean = tool.url
    .replace("https://", "")
    .replace("http://", "")
    .replace("www.", "")
    .replace(/\/$/, "");

  const handleOpen = async () => {
    setOpening(true);
    try {
      await onOpen(tool.id);
    } finally {
      setOpening(false);
    }
  };

  return (
    <div
      className="relative flex flex-col gap-2 p-4 rounded-2xl border border-[#1E293B] bg-[#0F172A] hover:bg-[#1A3A5C] hover:border-[#2563EB] transition-all cursor-pointer group"
      style={{ minWidth: 260, maxWidth: 300 }}
      onClick={handleOpen}
    >
      {/* Actions */}
      <div className="absolute top-3 right-3 flex gap-1.5" onClick={(e) => e.stopPropagation()}>
        <button
          onClick={() => onFavorite(tool.id)}
          className="text-lg leading-none hover:scale-110 transition-transform"
          title={tool.is_favorite ? "Remover dos favoritos" : "Favoritar"}
        >
          {tool.is_favorite ? "❤️" : "🤍"}
        </button>
        {isAdmin && (
          <button
            onClick={() => onDelete(tool.id)}
            className="text-slate-500 hover:text-red-400 transition-colors"
            title="Excluir"
          >
            <Trash2 size={15} />
          </button>
        )}
      </div>

      {/* Icon + name */}
      <div className="flex items-center gap-3 mt-1">
        <div
          className="w-11 h-11 rounded-full flex items-center justify-center text-white font-bold text-lg shrink-0"
          style={{ background: `linear-gradient(135deg, #1A3A5C, #2563EB)` }}
        >
          {tool.name[0].toUpperCase()}
        </div>
        <div className="min-w-0">
          <p className="font-semibold text-white text-sm truncate">{tool.name}</p>
          <p className="text-slate-400 text-xs truncate">{urlClean.length > 28 ? urlClean.slice(0, 26) + "…" : urlClean}</p>
        </div>
      </div>

      {/* Tags */}
      <div className="flex items-center gap-1.5 flex-wrap mt-1">
        <span
          className="text-[11px] font-semibold text-white px-2.5 py-0.5 rounded-full"
          style={{ backgroundColor: color }}
        >
          {tool.category}
        </span>
        {(tool.tags || []).slice(0, 1).map((tag) => (
          <span key={tag} className="text-[11px] bg-[#1E293B] text-slate-300 px-2 py-0.5 rounded-full">
            {tag}
          </span>
        ))}
      </div>

      {/* Open indicator */}
      <div className="flex items-center justify-end text-[11px] text-slate-500 group-hover:text-slate-300 transition-colors mt-auto pt-1">
        {opening ? (
          <Loader2 size={13} className="animate-spin" />
        ) : (
          <><ExternalLink size={11} className="mr-1" /> Abrir no Chrome</>
        )}
      </div>
    </div>
  );
}

// ── ToolListItem ──────────────────────────────────────────────────────────────
function ToolListItem({ tool, onOpen, onFavorite, onDelete, isAdmin }) {
  const color = CATEGORY_COLORS[tool.category] || "#334155";

  return (
    <div
      className="flex items-center gap-4 px-4 py-3 rounded-xl border border-[#1E293B] bg-[#0F172A] hover:bg-[#1A3A5C] hover:border-[#2563EB] transition-all cursor-pointer"
      onClick={() => onOpen(tool.id)}
    >
      <div
        className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold shrink-0"
        style={{ background: "linear-gradient(135deg, #1A3A5C, #2563EB)" }}
      >
        {tool.name[0].toUpperCase()}
      </div>

      <div className="w-40 shrink-0">
        <p className="font-semibold text-white text-sm truncate">{tool.name}</p>
        <p className="text-slate-400 text-xs truncate">
          {tool.url.replace("https://", "").replace("http://", "").slice(0, 30)}
        </p>
      </div>

      <span
        className="text-[11px] font-semibold text-white px-3 py-1 rounded-full shrink-0"
        style={{ backgroundColor: color }}
      >
        {tool.category}
      </span>

      <div className="flex-1" />

      <div className="flex items-center gap-2 shrink-0" onClick={(e) => e.stopPropagation()}>
        <button onClick={() => onFavorite(tool.id)} className="text-base">
          {tool.is_favorite ? "❤️" : "🤍"}
        </button>
        {isAdmin && (
          <button
            onClick={() => onDelete(tool.id)}
            className="text-slate-500 hover:text-red-400"
          >
            <Trash2 size={15} />
          </button>
        )}
      </div>
    </div>
  );
}

// ── PanelPage ─────────────────────────────────────────────────────────────────
export default function PanelPage() {
  const {
    loading, category, search, viewMode,
    setCategory, setSearch, setViewMode,
    fetchTools, toggleFavorite, deleteTool, openTool, filteredTools,
  } = useToolsStore();

  const isAdmin = useAuthStore((s) => s.isAdmin());
  const [jobWatcher, setJobWatcher] = useState(null);

  useEffect(() => {
    fetchTools();
  }, [category]);

  const handleOpen = useCallback(async (toolId) => {
    const toastId = toast.loading("Iniciando Chrome...");
    try {
      const jobId = await openTool(toolId);
      toast.loading("Abrindo ferramenta...", { id: toastId });

      // WebSocket para acompanhar progresso
      const { user, accessToken } = useAuthStore.getState();
      const wsUrl = `${import.meta.env.VITE_WS_URL || "ws://localhost:8000"}/api/worker/ws/${jobId}?token=${accessToken}`;
      const ws = new WebSocket(wsUrl);

      ws.onmessage = (e) => {
        const event = JSON.parse(e.data);
        if (event.type === "opened") {
          toast.success(`${event.data.tool_name || "Ferramenta"} aberta!`, { id: toastId });
          ws.close();
        } else if (event.type === "error") {
          toast.error(event.data.message || "Erro ao abrir", { id: toastId });
          ws.close();
        } else if (event.type === "starting") {
          toast.loading(event.data.message, { id: toastId });
        }
      };

      ws.onerror = () => {
        toast.error("Erro de conexão com o worker", { id: toastId });
      };

    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erro ao abrir ferramenta", { id: toastId });
    }
  }, []);

  const handleFavorite = async (toolId) => {
    await toggleFavorite(toolId);
    toast.success("Favorito atualizado");
  };

  const handleDelete = async (toolId) => {
    if (!confirm("Excluir esta ferramenta?")) return;
    await deleteTool(toolId);
    toast.success("Ferramenta removida");
  };

  const tools = filteredTools();

  return (
    <div className="flex h-full">
      {/* Category sidebar */}
      <aside className="w-56 shrink-0 bg-[#0B1120] border-r border-[#1E293B] py-4 px-2 overflow-y-auto">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.id}
            onClick={() => setCategory(cat.id)}
            className={clsx(
              "w-full text-left px-3 py-2.5 rounded-lg text-sm font-medium transition-colors mb-0.5",
              category === cat.id
                ? "bg-[#2563EB] text-white"
                : "text-slate-400 hover:bg-[#1E293B] hover:text-white"
            )}
          >
            {cat.label}
          </button>
        ))}
      </aside>

      {/* Content */}
      <div className="flex-1 flex flex-col overflow-hidden p-6 gap-4">
        {/* Toolbar */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-md">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Pesquisar ferramentas..."
              className="w-full pl-9 pr-4 py-2 bg-[#1E293B] border border-[#1E293B] rounded-full text-sm text-white placeholder-slate-500 focus:outline-none focus:border-[#2563EB]"
            />
          </div>

          <div className="flex gap-1 bg-[#1E293B] rounded-lg p-1">
            <button
              onClick={() => setViewMode("cards")}
              className={clsx("p-1.5 rounded", viewMode === "cards" ? "bg-[#2563EB] text-white" : "text-slate-400 hover:text-white")}
            >
              <LayoutGrid size={16} />
            </button>
            <button
              onClick={() => setViewMode("list")}
              className={clsx("p-1.5 rounded", viewMode === "list" ? "bg-[#2563EB] text-white" : "text-slate-400 hover:text-white")}
            >
              <List size={16} />
            </button>
          </div>

          {isAdmin && (
            <button className="flex items-center gap-1.5 bg-[#2563EB] text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-[#1d4ed8] transition-colors">
              <Plus size={15} /> Nova IA
            </button>
          )}
        </div>

        {/* Title */}
        <h2 className="text-xl font-bold text-white border-b border-[#2563EB] pb-2">
          {CATEGORIES.find((c) => c.id === category)?.label || "Ferramentas"}
        </h2>

        {/* Tools grid/list */}
        {loading ? (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 size={32} className="animate-spin text-[#2563EB]" />
          </div>
        ) : tools.length === 0 ? (
          <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
            Nenhuma ferramenta encontrada.
          </div>
        ) : viewMode === "cards" ? (
          <div className="flex-1 overflow-auto">
            <div className="flex flex-wrap gap-5">
              {tools.map((tool) => (
                <ToolCard
                  key={tool.id}
                  tool={tool}
                  onOpen={handleOpen}
                  onFavorite={handleFavorite}
                  onDelete={handleDelete}
                  isAdmin={isAdmin}
                />
              ))}
            </div>
          </div>
        ) : (
          <div className="flex-1 overflow-auto flex flex-col gap-2">
            {tools.map((tool) => (
              <ToolListItem
                key={tool.id}
                tool={tool}
                onOpen={handleOpen}
                onFavorite={handleFavorite}
                onDelete={handleDelete}
                isAdmin={isAdmin}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
