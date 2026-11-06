import React, { useState, useEffect } from 'react';
import {
  FileText,
  Compass,
  GitCompare,
  BookMarked,
  ArrowRight,
  Upload,
  CheckCircle2,
  Layers,
  Sparkles,
} from 'lucide-react';
import { api } from '../../services/api';
import { DocumentItem, UserUsage } from '../../types';
import { NavigationTab } from '../../components/layout/Sidebar';
import { StatusBadge } from '../../components/common/StatusBadge';

interface DashboardViewProps {
  onNavigate: (tab: NavigationTab) => void;
  onOpenUpload: () => void;
  refreshTrigger?: number;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  onNavigate,
  onOpenUpload,
  refreshTrigger = 0,
}) => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [usage, setUsage] = useState<UserUsage | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    loadDashboardData();
  }, [refreshTrigger]);

  const loadDashboardData = async () => {
    try {
      const [docsData, usageData] = await Promise.all([
        api.listDocuments(),
        api.getUsage(),
      ]);
      setDocuments(docsData.items.slice(0, 5));
      setUsage(usageData);
      setIsLoading(false);
    } catch (err) {
      console.error('Failed to load dashboard:', err);
      setIsLoading(false);
    }
  };

  return (
    <div className="p-4 sm:p-6 md:p-8 max-w-6xl mx-auto space-y-6 sm:space-y-8">
      {/* Editorial Welcome Header */}
      <div className="border-b border-parchment-300 pb-4 sm:pb-6">
        <span className="text-[10px] sm:text-[11px] font-mono uppercase tracking-wider text-navy-800 font-bold bg-navy-50 px-2 py-0.5 rounded border border-navy-200">
          ORION Research Assistant
        </span>
        <h1 className="text-2xl sm:text-3xl font-serif font-bold text-ink-950 mt-2">
          Research Deeper. Verify Every Answer.
        </h1>
        <p className="text-xs text-ink-600 mt-1 max-w-2xl leading-relaxed">
          Upload scientific PDFs, pose complex queries, compare multiple documents, and inspect strict page-level citations without hallucination.
        </p>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 bg-white rounded-xl border border-parchment-300 shadow-xs">
          <span className="text-xs text-ink-500 font-mono block mb-1">Indexed Papers</span>
          <span className="text-2xl font-serif font-bold text-ink-950">
            {usage?.completed_document_count ?? 0}
          </span>
          <span className="text-[10px] text-ink-400 font-mono block mt-0.5">
            of {usage?.document_count ?? 0} total uploaded
          </span>
        </div>

        <div className="p-4 bg-white rounded-xl border border-parchment-300 shadow-xs">
          <span className="text-xs text-ink-500 font-mono block mb-1">Pages Extracted</span>
          <span className="text-2xl font-serif font-bold text-ink-950">
            {usage?.total_pages_ingested ?? 0}
          </span>
          <span className="text-[10px] text-ink-400 font-mono block mt-0.5">
            page-by-page provenance
          </span>
        </div>

        <div className="p-4 bg-white rounded-xl border border-parchment-300 shadow-xs">
          <span className="text-xs text-ink-500 font-mono block mb-1">Vector Chunks</span>
          <span className="text-2xl font-serif font-bold text-ink-950">
            {usage?.total_chunks_indexed ?? 0}
          </span>
          <span className="text-[10px] text-ink-400 font-mono block mt-0.5">
            384-dim BGE embeddings
          </span>
        </div>

        <div className="p-4 bg-white rounded-xl border border-parchment-300 shadow-xs">
          <span className="text-xs text-ink-500 font-mono block mb-1">Saved Notes</span>
          <span className="text-2xl font-serif font-bold text-ink-950">
            {usage?.note_count ?? 0}
          </span>
          <span className="text-[10px] text-ink-400 font-mono block mt-0.5">
            evidence-grounded notes
          </span>
        </div>
      </div>

      {/* Quick Launchpad Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div
          onClick={() => onNavigate('research')}
          className="p-5 bg-white rounded-xl border border-parchment-300 hover:border-navy-500 hover:shadow-subtle cursor-pointer transition-all space-y-3 group"
        >
          <div className="w-10 h-10 rounded-lg bg-navy-100 flex items-center justify-center text-navy-800 group-hover:scale-105 transition-transform">
            <Compass className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-serif font-bold text-ink-950 group-hover:text-navy-900 flex items-center justify-between">
              <span>Research Workspace</span>
              <ArrowRight className="w-4 h-4 text-ink-400 group-hover:translate-x-1 transition-transform" />
            </h3>
            <p className="text-xs text-ink-500 mt-1">
              Ask natural-language questions across papers with live page citations.
            </p>
          </div>
        </div>

        <div
          onClick={() => onNavigate('compare')}
          className="p-5 bg-white rounded-xl border border-parchment-300 hover:border-navy-500 hover:shadow-subtle cursor-pointer transition-all space-y-3 group"
        >
          <div className="w-10 h-10 rounded-lg bg-forest-100 flex items-center justify-center text-forest-800 group-hover:scale-105 transition-transform">
            <GitCompare className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-serif font-bold text-ink-950 group-hover:text-navy-900 flex items-center justify-between">
              <span>Paper Comparison</span>
              <ArrowRight className="w-4 h-4 text-ink-400 group-hover:translate-x-1 transition-transform" />
            </h3>
            <p className="text-xs text-ink-500 mt-1">
              Side-by-side analysis of methodology, datasets, results, and limitations.
            </p>
          </div>
        </div>

        <div
          onClick={onOpenUpload}
          className="p-5 bg-white rounded-xl border border-dashed border-parchment-400 hover:border-navy-600 hover:bg-parchment-50/50 cursor-pointer transition-all space-y-3 group"
        >
          <div className="w-10 h-10 rounded-lg bg-parchment-200 flex items-center justify-center text-ink-800 group-hover:scale-105 transition-transform">
            <Upload className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-serif font-bold text-ink-950 flex items-center justify-between">
              <span>Upload New PDF</span>
              <ArrowRight className="w-4 h-4 text-ink-400 group-hover:translate-x-1 transition-transform" />
            </h3>
            <p className="text-xs text-ink-500 mt-1">
              Ingest preprints, publications, and technical reports.
            </p>
          </div>
        </div>
      </div>

      {/* Recent Documents Table Preview */}
      <div className="bg-white rounded-xl border border-parchment-300 shadow-xs overflow-hidden">
        <div className="px-6 py-4 border-b border-parchment-200 bg-parchment-50 flex items-center justify-between">
          <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-ink-800">
            Recent Research Documents
          </h2>
          <button
            type="button"
            onClick={() => onNavigate('documents')}
            className="text-xs font-mono text-navy-800 hover:underline"
          >
            View All Documents →
          </button>
        </div>

        {documents.length === 0 ? (
          <div className="p-8 text-center text-xs text-ink-400">
            No research papers uploaded yet. Click "Upload New PDF" above to begin.
          </div>
        ) : (
          <div className="divide-y divide-parchment-200">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="px-4 sm:px-6 py-3 sm:py-3.5 flex items-center justify-between hover:bg-parchment-50 transition-colors text-xs gap-2"
              >
                <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
                  <FileText className="w-4 h-4 text-navy-700 shrink-0" />
                  <span className="font-medium text-ink-950 truncate max-w-[160px] xs:max-w-xs sm:max-w-sm">
                    {doc.filename}
                  </span>
                </div>
                <div className="flex items-center gap-2 sm:gap-4 shrink-0">
                  <span className="font-mono text-ink-400 text-[10px] sm:text-[11px] hidden xs:inline">
                    {doc.page_count} pp • {doc.chunk_count} chunks
                  </span>
                  <StatusBadge status={doc.status} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
