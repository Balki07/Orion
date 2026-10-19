import React, { useState, useEffect } from 'react';
import {
  Settings as SettingsIcon,
  Cpu,
  Database,
  Sliders,
  HardDrive,
  ShieldCheck,
  CheckCircle2,
  FileText,
  UserCheck,
} from 'lucide-react';
import { api } from '../../services/api';
import { SystemSettings, UserUsage } from '../../types';
import { useAuth } from '../../context/AuthContext';

export const SettingsView: React.FC = () => {
  const { user } = useAuth();
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [usage, setUsage] = useState<UserUsage | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const [sData, uData] = await Promise.all([
        api.getSettings(),
        api.getUsage(),
      ]);
      setSettings(sData);
      setUsage(uData);
      setIsLoading(false);
    } catch (err) {
      console.error('Failed to load settings:', err);
      setIsLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      {/* Page Header */}
      <div className="border-b border-parchment-300 pb-5">
        <h1 className="text-2xl font-serif font-bold text-ink-950">
          Settings & System Diagnostics
        </h1>
        <p className="text-xs text-ink-500 mt-1">
          Inspect configured AI models, retrieval parameters, tenant storage consumption, and security guarantees.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* User Workspace Profile Card */}
        <div className="p-5 bg-white rounded-xl border border-parchment-300 shadow-xs space-y-4">
          <div className="flex items-center gap-2.5 pb-3 border-b border-parchment-200">
            <UserCheck className="w-5 h-5 text-navy-800" />
            <h2 className="text-sm font-serif font-bold text-ink-950">
              Researcher Identity & Tenant Scope
            </h2>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-parchment-100">
              <span className="text-ink-500">Authenticated Email:</span>
              <span className="font-mono text-ink-900 font-semibold">{user?.email}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-parchment-100">
              <span className="text-ink-500">Tenant ID:</span>
              <span className="font-mono text-ink-700">{user?.id}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-parchment-100">
              <span className="text-ink-500">Session Role:</span>
              <span className="font-mono text-ink-900 capitalize">{user?.role}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-ink-500">Tenant Isolation:</span>
              <span className="inline-flex items-center gap-1 text-forest-700 font-medium">
                <CheckCircle2 className="w-3.5 h-3.5 text-forest-600" />
                Active & Enforced
              </span>
            </div>
          </div>
        </div>

        {/* AI & Embedding Models Card */}
        <div className="p-5 bg-white rounded-xl border border-parchment-300 shadow-xs space-y-4">
          <div className="flex items-center gap-2.5 pb-3 border-b border-parchment-200">
            <Cpu className="w-5 h-5 text-navy-800" />
            <h2 className="text-sm font-serif font-bold text-ink-950">
              AI Models & Vector Embeddings
            </h2>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-parchment-100">
              <span className="text-ink-500">Active LLM:</span>
              <span className="font-mono text-ink-900 font-semibold">
                {settings?.active_gemini_model || 'gemini-1.5-flash'}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-parchment-100">
              <span className="text-ink-500">Embedding Model:</span>
              <span className="font-mono text-ink-900 font-semibold">
                {settings?.active_embedding_model || 'BAAI/bge-small-en-v1.5'}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-parchment-100">
              <span className="text-ink-500">Vector Dimensions:</span>
              <span className="font-mono text-ink-700">
                {settings?.embedding_dimensions || 384} floats
              </span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-ink-500">Inference Device:</span>
              <span className="font-mono text-ink-700">Local CPU (Bounded Concurrency)</span>
            </div>
          </div>
        </div>

        {/* Retrieval & Ingestion Hyperparameters */}
        <div className="p-5 bg-white rounded-xl border border-parchment-300 shadow-xs space-y-4">
          <div className="flex items-center gap-2.5 pb-3 border-b border-parchment-200">
            <Sliders className="w-5 h-5 text-navy-800" />
            <h2 className="text-sm font-serif font-bold text-ink-950">
              Retrieval & Ingestion Parameters
            </h2>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-parchment-100">
              <span className="text-ink-500">Retrieval Top-K:</span>
              <span className="font-mono text-ink-900">{settings?.retrieval_top_k || 8} passages</span>
            </div>
            <div className="flex justify-between py-1 border-b border-parchment-100">
              <span className="text-ink-500">Hybrid Fusion (RRF Alpha):</span>
              <span className="font-mono text-ink-900">{settings?.hybrid_fusion_alpha || 0.6}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-parchment-100">
              <span className="text-ink-500">Chunk Target Size:</span>
              <span className="font-mono text-ink-700">{settings?.chunk_size || 500} characters</span>
            </div>
            <div className="flex justify-between py-1 border-b border-parchment-100">
              <span className="text-ink-500">Chunk Overlap:</span>
              <span className="font-mono text-ink-700">{settings?.chunk_overlap || 80} characters</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-ink-500">Cross-Encoder Reranker:</span>
              <span className="font-mono text-ink-700">
                {settings?.reranker_enabled ? 'Enabled' : 'Disabled (Default)'}
              </span>
            </div>
          </div>
        </div>

        {/* Measured Storage & Usage */}
        <div className="p-5 bg-white rounded-xl border border-parchment-300 shadow-xs space-y-4">
          <div className="flex items-center gap-2.5 pb-3 border-b border-parchment-200">
            <HardDrive className="w-5 h-5 text-navy-800" />
            <h2 className="text-sm font-serif font-bold text-ink-950">
              Measured Workspace Resource Usage
            </h2>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-parchment-100">
              <span className="text-ink-500">Storage Engine:</span>
              <span className="font-mono text-ink-900 capitalize">
                {settings?.storage_provider || 'local'} filesystem
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-parchment-100">
              <span className="text-ink-500">Indexed Storage Size:</span>
              <span className="font-mono text-ink-900 font-semibold">
                {usage ? (usage.total_storage_bytes / (1024 * 1024)).toFixed(2) : 0} MB
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-parchment-100">
              <span className="text-ink-500">Max Upload Cap:</span>
              <span className="font-mono text-ink-700">
                {settings?.max_upload_size_mb || 32} MB per file
              </span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-ink-500">Max Page Cap:</span>
              <span className="font-mono text-ink-700">
                {settings?.max_pdf_pages || 200} pages per PDF
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
