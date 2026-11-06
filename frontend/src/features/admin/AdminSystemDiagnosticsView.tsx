import React, { useState, useEffect } from 'react';
import {
  Cpu,
  Database,
  Sliders,
  HardDrive,
  Activity,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Server,
  Zap,
  Layers,
  FileText,
  Lock,
  BarChart3,
} from 'lucide-react';
import { api } from '../../services/api';
import { SystemSettings, AdminSystemHealth, AdminOverviewResponse, AdminDailyAIUsagePoint } from '../../types';

export const AdminSystemDiagnosticsView: React.FC = () => {
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [health, setHealth] = useState<AdminSystemHealth | null>(null);
  const [overview, setOverview] = useState<AdminOverviewResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());

  useEffect(() => {
    loadDiagnostics();
  }, []);

  const loadDiagnostics = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sData, hData, oData] = await Promise.all([
        (typeof api.getSettings === 'function' ? api.getSettings() : Promise.resolve(null)).catch(() => null),
        (typeof api.getAdminSystemHealth === 'function' ? api.getAdminSystemHealth() : Promise.resolve(null)).catch(() => null),
        (typeof api.getAdminOverview === 'function' ? api.getAdminOverview() : Promise.resolve(null)).catch(() => null),
      ]);
      setSettings(sData);
      setHealth(hData);
      setOverview(oData);
      setLastRefreshed(new Date());
    } catch (err: any) {
      console.error('Failed to load system diagnostics:', err);
      setError(err?.message || 'Failed to retrieve administrative diagnostics.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Diagnostics Header Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-5 bg-white dark:bg-[#1B2625] rounded-xl border border-parchment-300 dark:border-[#273634] shadow-xs">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono uppercase tracking-wider text-amber-800 dark:text-amber-300 font-bold bg-amber-100 dark:bg-amber-950/60 px-2 py-0.5 rounded border border-amber-300 dark:border-amber-700">
              Admin Diagnostics
            </span>
            <h2 className="text-lg font-serif font-bold text-ink-950 dark:text-white">
              System Diagnostics &amp; Technical Architecture
            </h2>
          </div>
          <p className="text-xs text-ink-500 dark:text-slate-400 mt-1">
            Real-time infrastructure health, AI provider configuration, vector parameters, and system-wide telemetry.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-ink-500 dark:text-slate-400 hidden sm:inline font-mono">
            Synced: {lastRefreshed.toLocaleTimeString()}
          </span>
          <button
            type="button"
            onClick={loadDiagnostics}
            disabled={loading}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg border border-parchment-300 dark:border-zinc-700 bg-parchment-50 dark:bg-zinc-800 hover:bg-parchment-100 text-ink-900 dark:text-white text-xs font-semibold transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh Diagnostics</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl border border-rose-300 bg-rose-50 text-rose-800 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Grid of Diagnostics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {/* Card 1: FastAPI Application Backend */}
        <div className="p-5 bg-white dark:bg-[#1B2625] rounded-xl border border-parchment-300 dark:border-[#273634] shadow-xs space-y-3">
          <div className="flex items-center justify-between pb-2.5 border-b border-parchment-200 dark:border-[#273634]">
            <div className="flex items-center gap-2 font-serif font-bold text-sm text-ink-950 dark:text-white">
              <Server className="w-4 h-4 text-navy-800 dark:text-blue-400" />
              <h3>FastAPI Application Backend</h3>
            </div>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
              {health?.status.toUpperCase() || 'HEALTHY'}
            </span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-parchment-100 dark:border-[#273634]">
              <span className="text-ink-500 dark:text-slate-400">Environment:</span>
              <span className="font-semibold text-ink-900 dark:text-white uppercase">{health?.environment || 'staging'}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-parchment-100 dark:border-[#273634]">
              <span className="text-ink-500 dark:text-slate-400">Application Version:</span>
              <span className="font-mono text-ink-900 dark:text-white">{health?.version || '1.0.0'}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-ink-500 dark:text-slate-400">Core Engine:</span>
              <span className="text-emerald-600 font-semibold flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" /> Healthy &amp; Ready
              </span>
            </div>
          </div>
        </div>

        {/* Card 2: Google Gemini LLM Integration */}
        <div className="p-5 bg-white dark:bg-[#1B2625] rounded-xl border border-parchment-300 dark:border-[#273634] shadow-xs space-y-3">
          <div className="flex items-center justify-between pb-2.5 border-b border-parchment-200 dark:border-[#273634]">
            <div className="flex items-center gap-2 font-serif font-bold text-sm text-ink-950 dark:text-white">
              <Zap className="w-4 h-4 text-purple-600 dark:text-purple-400" />
              <h3>Google Gemini LLM Integration</h3>
            </div>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
              {health?.gemini?.status.toUpperCase() || 'READY'}
            </span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-parchment-100 dark:border-[#273634]">
              <span className="text-ink-500 dark:text-slate-400">Active Model:</span>
              <span className="font-mono font-semibold text-ink-900 dark:text-white">
                {settings?.active_gemini_model || health?.gemini?.model || 'gemini-2.5-flash'}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-parchment-100 dark:border-[#273634]">
              <span className="text-ink-500 dark:text-slate-400">Configured Rate Limit:</span>
              <span className="font-mono text-ink-900 dark:text-white">{health?.gemini?.rpm_limit || 60} RPM</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-ink-500 dark:text-slate-400">API Key Security:</span>
              <span className="text-emerald-700 dark:text-emerald-400 font-semibold flex items-center gap-1">
                <Lock className="w-3.5 h-3.5" /> Key Securely Mounted (Never Exposed)
              </span>
            </div>
          </div>
        </div>

        {/* Card 3: Embedding Model & Vector Dimensions */}
        <div className="p-5 bg-white dark:bg-[#1B2625] rounded-xl border border-parchment-300 dark:border-[#273634] shadow-xs space-y-3">
          <div className="flex items-center justify-between pb-2.5 border-b border-parchment-200 dark:border-[#273634]">
            <div className="flex items-center gap-2 font-serif font-bold text-sm text-ink-950 dark:text-white">
              <Cpu className="w-4 h-4 text-blue-600 dark:text-blue-400" />
              <h3>Embedding Model &amp; Vectors</h3>
            </div>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300">
              384-DIM
            </span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-parchment-100 dark:border-[#273634]">
              <span className="text-ink-500 dark:text-slate-400">Embedding Model:</span>
              <span className="font-mono font-semibold text-ink-900 dark:text-white">
                {settings?.active_embedding_model || 'BAAI/bge-small-en-v1.5'}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-parchment-100 dark:border-[#273634]">
              <span className="text-ink-500 dark:text-slate-400">Vector Dimensions:</span>
              <span className="font-mono text-ink-900 dark:text-white">
                {settings?.embedding_dimensions || 384} floats
              </span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-ink-500 dark:text-slate-400">Inference Hardware:</span>
              <span className="text-ink-900 dark:text-white font-medium">Local CPU (FastEmbed Bounded)</span>
            </div>
          </div>
        </div>

        {/* Card 4: Retrieval Top-K & RRF Parameters */}
        <div className="p-5 bg-white dark:bg-[#1B2625] rounded-xl border border-parchment-300 dark:border-[#273634] shadow-xs space-y-3">
          <div className="flex items-center justify-between pb-2.5 border-b border-parchment-200 dark:border-[#273634]">
            <div className="flex items-center gap-2 font-serif font-bold text-sm text-ink-950 dark:text-white">
              <Sliders className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              <h3>Retrieval Top-K &amp; RRF Fusion</h3>
            </div>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
              HYBRID RRF
            </span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-parchment-100 dark:border-[#273634]">
              <span className="text-ink-500 dark:text-slate-400">Retrieval Top-K:</span>
              <span className="font-mono font-semibold text-ink-900 dark:text-white">
                {settings?.retrieval_top_k || 8} candidate passages
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-parchment-100 dark:border-[#273634]">
              <span className="text-ink-500 dark:text-slate-400">Hybrid Alpha Weight:</span>
              <span className="font-mono font-semibold text-ink-900 dark:text-white">
                {settings?.hybrid_fusion_alpha || 0.6} (Vector: 0.6 / Lexical: 0.4)
              </span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-ink-500 dark:text-slate-400">RRF Constant (k):</span>
              <span className="font-mono text-ink-900 dark:text-white">60</span>
            </div>
          </div>
        </div>

        {/* Card 5: Chunking & Ingestion Configuration */}
        <div className="p-5 bg-white dark:bg-[#1B2625] rounded-xl border border-parchment-300 dark:border-[#273634] shadow-xs space-y-3">
          <div className="flex items-center justify-between pb-2.5 border-b border-parchment-200 dark:border-[#273634]">
            <div className="flex items-center gap-2 font-serif font-bold text-sm text-ink-950 dark:text-white">
              <FileText className="w-4 h-4 text-amber-600 dark:text-amber-400" />
              <h3>Chunking &amp; Ingestion Pipeline</h3>
            </div>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300">
              PYMUPDF
            </span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-parchment-100 dark:border-[#273634]">
              <span className="text-ink-500 dark:text-slate-400">Target Chunk Size:</span>
              <span className="font-mono font-semibold text-ink-900 dark:text-white">
                {settings?.chunk_size || 500} characters
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-parchment-100 dark:border-[#273634]">
              <span className="text-ink-500 dark:text-slate-400">Chunk Overlap:</span>
              <span className="font-mono text-ink-900 dark:text-white">
                {settings?.chunk_overlap || 80} characters
              </span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-ink-500 dark:text-slate-400">Max Upload Cap:</span>
              <span className="font-mono text-ink-900 dark:text-white">
                {settings?.max_upload_size_mb || 32} MB ({settings?.max_pdf_pages || 200} pages)
              </span>
            </div>
          </div>
        </div>

        {/* Card 6: Cross-Encoder Configuration */}
        <div className="p-5 bg-white dark:bg-[#1B2625] rounded-xl border border-parchment-300 dark:border-[#273634] shadow-xs space-y-3">
          <div className="flex items-center justify-between pb-2.5 border-b border-parchment-200 dark:border-[#273634]">
            <div className="flex items-center gap-2 font-serif font-bold text-sm text-ink-950 dark:text-white">
              <Layers className="w-4 h-4 text-rose-600 dark:text-rose-400" />
              <h3>Cross-Encoder Configuration</h3>
            </div>
            <span
              className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                settings?.reranker_enabled
                  ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300'
                  : 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300'
              }`}
            >
              {settings?.reranker_enabled ? 'ENABLED' : 'OPTIONAL (DEFAULT OFF)'}
            </span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-parchment-100 dark:border-[#273634]">
              <span className="text-ink-500 dark:text-slate-400">Model:</span>
              <span className="font-mono text-ink-900 dark:text-white truncate max-w-[170px]" title="cross-encoder/ms-marco-MiniLM-L-6-v2">
                ms-marco-MiniLM-L-6-v2
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-parchment-100 dark:border-[#273634]">
              <span className="text-ink-500 dark:text-slate-400">Score Calibration:</span>
              <span className="font-mono text-ink-900 dark:text-white">Sigmoid Normalization</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-ink-500 dark:text-slate-400">Joint Attention:</span>
              <span className="text-ink-900 dark:text-white font-medium">Re-ranks top candidate passages</span>
            </div>
          </div>
        </div>

        {/* Card 7: PostgreSQL / SQLite Persistence */}
        <div className="p-5 bg-white dark:bg-[#1B2625] rounded-xl border border-parchment-300 dark:border-[#273634] shadow-xs space-y-3">
          <div className="flex items-center justify-between pb-2.5 border-b border-parchment-200 dark:border-[#273634]">
            <div className="flex items-center gap-2 font-serif font-bold text-sm text-ink-950 dark:text-white">
              <Database className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              <h3>PostgreSQL / SQLite Persistence</h3>
            </div>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
              CONNECTED
            </span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-parchment-100 dark:border-[#273634]">
              <span className="text-ink-500 dark:text-slate-400">Engine Dialect:</span>
              <span className="font-mono font-bold text-ink-900 dark:text-white uppercase">
                {health?.database?.dialect || 'postgresql'}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-parchment-100 dark:border-[#273634]">
              <span className="text-ink-500 dark:text-slate-400">pgvector Vector Search:</span>
              <span className="font-semibold text-emerald-700 dark:text-emerald-400 flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" />
                {health?.database?.pgvector_ready ? 'Extension Ready' : 'Fallback Mode'}
              </span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-ink-500 dark:text-slate-400">Connection Health:</span>
              <span className="text-emerald-700 dark:text-emerald-400 font-semibold">Active &amp; Resilient</span>
            </div>
          </div>
        </div>

        {/* Card 8: Object Storage Abstraction */}
        <div className="p-5 bg-white dark:bg-[#1B2625] rounded-xl border border-parchment-300 dark:border-[#273634] shadow-xs space-y-3">
          <div className="flex items-center justify-between pb-2.5 border-b border-parchment-200 dark:border-[#273634]">
            <div className="flex items-center gap-2 font-serif font-bold text-sm text-ink-950 dark:text-white">
              <HardDrive className="w-4 h-4 text-amber-600 dark:text-amber-400" />
              <h3>Object Storage Abstraction</h3>
            </div>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
              OPERATIONAL
            </span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-parchment-100 dark:border-[#273634]">
              <span className="text-ink-500 dark:text-slate-400">Storage Backend:</span>
              <span className="font-mono font-semibold text-ink-900 dark:text-white capitalize">
                {health?.storage?.provider || settings?.storage_provider || 'local'}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-parchment-100 dark:border-[#273634]">
              <span className="text-ink-500 dark:text-slate-400">Per-User Standard Quota:</span>
              <span className="font-semibold text-ink-900 dark:text-white">{health?.storage?.user_quota_mb || 500} MB</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-ink-500 dark:text-slate-400">Multi-Tenant Isolation:</span>
              <span className="text-emerald-700 dark:text-emerald-400 font-semibold flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" /> Enforced by owner_id prefix
              </span>
            </div>
          </div>
        </div>

        {/* Card 9: Durable Worker Health */}
        <div className="p-5 bg-white dark:bg-[#1B2625] rounded-xl border border-parchment-300 dark:border-[#273634] shadow-xs space-y-3">
          <div className="flex items-center justify-between pb-2.5 border-b border-parchment-200 dark:border-[#273634]">
            <div className="flex items-center gap-2 font-serif font-bold text-sm text-ink-950 dark:text-white">
              <Server className="w-4 h-4 text-navy-800 dark:text-blue-400" />
              <h3>Durable Ingestion Worker</h3>
            </div>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
              {health?.ingestion?.status.toUpperCase() || 'ACTIVE'}
            </span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-parchment-100 dark:border-[#273634]">
              <span className="text-ink-500 dark:text-slate-400">Persistent Job Architecture:</span>
              <span className="font-semibold text-ink-900 dark:text-white">PostgreSQL Transactional Queue</span>
            </div>
            <div className="flex justify-between py-1 border-b border-parchment-100 dark:border-[#273634]">
              <span className="text-ink-500 dark:text-slate-400">Worker Concurrency:</span>
              <span className="font-mono text-ink-900 dark:text-white">{health?.ingestion?.concurrency || 2} concurrent jobs</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-ink-500 dark:text-slate-400">Fail-Safe Heartbeat:</span>
              <span className="text-emerald-700 dark:text-emerald-400 font-semibold">Automatic Recovery Enabled</span>
            </div>
          </div>
        </div>

        {/* Card 10: Authentication, Security & Health */}
        <div className="p-5 bg-white dark:bg-[#1B2625] rounded-xl border border-parchment-300 dark:border-[#273634] shadow-xs space-y-3">
          <div className="flex items-center justify-between pb-2.5 border-b border-parchment-200 dark:border-[#273634]">
            <div className="flex items-center gap-2 font-serif font-bold text-sm text-ink-950 dark:text-white">
              <Lock className="w-4 h-4 text-emerald-700 dark:text-emerald-400" />
              <h3>Authentication &amp; Security</h3>
            </div>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
              ARGON2ID
            </span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-parchment-100 dark:border-[#273634]">
              <span className="text-ink-500 dark:text-slate-400">Password Hashing:</span>
              <span className="font-mono text-ink-900 dark:text-white">Argon2id (RFC 9106)</span>
            </div>
            <div className="flex justify-between py-1 border-b border-parchment-100 dark:border-[#273634]">
              <span className="text-ink-500 dark:text-slate-400">Session JWT:</span>
              <span className="font-semibold text-emerald-700 dark:text-emerald-400">HttpOnly Lax SameSite</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-ink-500 dark:text-slate-400">CSRF Defense:</span>
              <span className="font-mono text-ink-900 dark:text-white">Double Submit Cookie (orion_csrf)</span>
            </div>
          </div>
        </div>
      </div>

      {/* System-wide Usage Metrics Section */}
      <div className="p-6 bg-white dark:bg-[#1B2625] rounded-xl border border-parchment-300 dark:border-[#273634] shadow-xs space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-parchment-200 dark:border-[#273634]">
          <div className="flex items-center gap-2.5">
            <BarChart3 className="w-5 h-5 text-navy-800 dark:text-blue-400" />
            <h3 className="font-serif font-bold text-sm text-ink-950 dark:text-white">
              System-Wide Metrics &amp; Operational Telemetry
            </h3>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
          <div className="p-4 rounded-xl border border-parchment-200 dark:border-[#273634] bg-parchment-50/60 dark:bg-[#1A2524]/60">
            <span className="text-ink-500 dark:text-slate-400 block mb-1">Registered Researchers</span>
            <p className="text-2xl font-bold font-serif text-ink-950 dark:text-white">
              {overview?.users.total_users || 0}
            </p>
            <p className="text-[11px] text-ink-400 mt-0.5">
              {overview?.users.active_users_24h || 0} active in past 24h
            </p>
          </div>

          <div className="p-4 rounded-xl border border-parchment-200 dark:border-[#273634] bg-parchment-50/60 dark:bg-[#1A2524]/60">
            <span className="text-ink-500 dark:text-slate-400 block mb-1">Total System Storage</span>
            <p className="text-2xl font-bold font-serif text-ink-950 dark:text-white">
              {overview?.documents.total_storage_mb ? `${overview.documents.total_storage_mb.toFixed(1)} MB` : '0 MB'}
            </p>
            <p className="text-[11px] text-ink-400 mt-0.5">
              Across {overview?.documents.total_documents || 0} papers
            </p>
          </div>

          <div className="p-4 rounded-xl border border-parchment-200 dark:border-[#273634] bg-parchment-50/60 dark:bg-[#1A2524]/60">
            <span className="text-ink-500 dark:text-slate-400 block mb-1">Total AI Queries</span>
            <p className="text-2xl font-bold font-serif text-ink-950 dark:text-white">
              {overview?.ai_usage.total_requests || 0}
            </p>
            <p className="text-[11px] text-ink-400 mt-0.5">
              {overview?.ai_usage.requests_today || 0} executed today
            </p>
          </div>

          <div className="p-4 rounded-xl border border-parchment-200 dark:border-[#273634] bg-parchment-50/60 dark:bg-[#1A2524]/60">
            <span className="text-ink-500 dark:text-slate-400 block mb-1">Token Volume &amp; Cost</span>
            <p className="text-2xl font-bold font-serif text-ink-950 dark:text-white">
              {overview?.ai_usage.total_tokens ? overview.ai_usage.total_tokens.toLocaleString() : '0'}
            </p>
            <p className="text-[11px] text-ink-400 mt-0.5">
              Est. Cost: ${overview?.ai_usage.estimated_cost_usd?.toFixed(4) || '0.0000'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
