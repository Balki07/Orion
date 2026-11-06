import React, { useState, useEffect, useCallback } from 'react';
import {
  FileText,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  BookOpen,
  X,
  Loader2,
  Sparkles,
  Layers,
  ShieldCheck,
} from 'lucide-react';
import { DemoPaperItem, DemoPageResponse } from '../../types';
import { api } from '../../services/api';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';

interface DemoPdfViewerProps {
  paper: DemoPaperItem;
  initialPage?: number;
  highlightPassage?: string;
  onClose: () => void;
}

export const DemoPdfViewer: React.FC<DemoPdfViewerProps> = ({
  paper,
  initialPage = 1,
  highlightPassage = '',
  onClose,
}) => {
  const [currentPage, setCurrentPage] = useState<number>(initialPage);
  const [viewMode, setViewMode] = useState<'text' | 'pdf'>('text');
  const [pageData, setPageData] = useState<DemoPageResponse | null>(null);
  const [isLoadingPage, setIsLoadingPage] = useState<boolean>(true);
  const [pageError, setPageError] = useState<string | null>(null);

  const totalPages = paper.total_pages || 5;

  // Sync current page if initialPage prop updates
  useEffect(() => {
    setCurrentPage(initialPage);
  }, [initialPage, paper.id]);

  // Fetch page text from public demo API
  const loadPageText = useCallback(
    async (page: number) => {
      setIsLoadingPage(true);
      setPageError(null);
      try {
        const data = await api.getDemoPaperPage(paper.id, page);
        setPageData(data);
      } catch (err: any) {
        setPageError(err?.message || 'Could not load extracted page text.');
      } finally {
        setIsLoadingPage(false);
      }
    },
    [paper.id]
  );

  useEffect(() => {
    loadPageText(currentPage);
  }, [currentPage, loadPageText]);

  const handlePrevPage = () => {
    if (currentPage > 1) setCurrentPage((p) => p - 1);
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) setCurrentPage((p) => p + 1);
  };

  // Render highlighted text if a passage matches
  const renderHighlightedContent = (text: string) => {
    if (!highlightPassage || !highlightPassage.trim()) {
      return <div className="whitespace-pre-wrap leading-relaxed">{text}</div>;
    }

    // Try finding the passage or keywords from it
    const cleanSnippet = highlightPassage.trim().slice(0, 80);
    const index = text.toLowerCase().indexOf(cleanSnippet.toLowerCase());

    if (index === -1) {
      return (
        <div className="space-y-4">
          <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded text-xs text-amber-700 dark:text-amber-300">
            <span className="font-semibold">Cited Passage Focus:</span> "{highlightPassage}"
          </div>
          <div className="whitespace-pre-wrap leading-relaxed">{text}</div>
        </div>
      );
    }

    const before = text.slice(0, index);
    const match = text.slice(index, index + cleanSnippet.length);
    const after = text.slice(index + cleanSnippet.length);

    return (
      <div className="whitespace-pre-wrap leading-relaxed">
        {before}
        <mark className="bg-amber-300/40 text-ink dark:bg-amber-400/30 rounded px-1 font-medium border-b-2 border-amber-500">
          {match}
        </mark>
        {after}
      </div>
    );
  };

  const pdfUrl = api.getDemoPaperPdfUrl(paper.id);

  return (
    <div
      className="flex flex-col h-full bg-paper-surface border-l border-border-hairline shadow-2xl overflow-hidden"
      role="region"
      aria-label="Demo Evidence Viewer"
    >
      {/* Top Header */}
      <div className="flex items-center justify-between p-3 sm:p-4 border-b border-border-hairline bg-paper-bg/60">
        <div className="flex items-center gap-2 min-w-0">
          <BookOpen className="w-5 h-5 text-amber-500 dark:text-[#ffb84c] shrink-0" />
          <div className="truncate">
            <h3 className="text-sm font-semibold text-ink truncate font-serif" title={paper.title}>
              {paper.title}
            </h3>
            <p className="text-xs text-ink-muted truncate">
              {paper.authors} ({paper.year}) • {paper.journal}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1 sm:gap-2 shrink-0">
          {paper.doi && (
            <a
              href={`https://doi.org/${paper.doi}`}
              target="_blank"
              rel="noopener noreferrer"
              className="hidden sm:inline-flex items-center gap-1 text-xs text-ink-secondary hover:text-amber-600 dark:hover:text-[#ffb84c] px-2 py-1 rounded border border-border-hairline"
              title="View on publisher website"
            >
              DOI <ExternalLink className="w-3 h-3" />
            </a>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="text-ink-muted hover:text-ink p-1.5"
            aria-label="Close Evidence Viewer"
          >
            <X className="w-5 h-5" />
          </Button>
        </div>
      </div>

      {/* Navigation & View Toggle Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2 border-b border-border-hairline bg-paper-bg/30 text-xs font-mono">
        {/* Page Switcher */}
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handlePrevPage}
            disabled={currentPage <= 1}
            className="h-7 w-7 p-0"
            aria-label="Previous Page"
          >
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <span className="text-ink-secondary">
            Page <strong className="text-ink">{currentPage}</strong> of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={handleNextPage}
            disabled={currentPage >= totalPages}
            className="h-7 w-7 p-0"
            aria-label="Next Page"
          >
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>

        {/* View Mode Switcher */}
        <div className="flex items-center gap-1 bg-paper-bg p-0.5 rounded border border-border-hairline">
          <button
            type="button"
            onClick={() => setViewMode('text')}
            className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs transition-colors ${
              viewMode === 'text'
                ? 'bg-paper-surface font-semibold text-ink shadow-sm'
                : 'text-ink-muted hover:text-ink'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            Extracted Text
          </button>
          <button
            type="button"
            onClick={() => setViewMode('pdf')}
            className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs transition-colors ${
              viewMode === 'pdf'
                ? 'bg-paper-surface font-semibold text-ink shadow-sm'
                : 'text-ink-muted hover:text-ink'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            PDF Binary
          </button>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 bg-paper-surface">
        {viewMode === 'text' ? (
          <div className="max-w-2xl mx-auto space-y-4 font-serif text-ink text-sm sm:text-base leading-relaxed">
            {isLoadingPage ? (
              <div className="flex flex-col items-center justify-center py-20 text-ink-muted gap-3">
                <Loader2 className="w-6 h-6 animate-spin text-amber-500 dark:text-[#ffb84c]" />
                <span className="text-xs font-mono">Extracting verified page text...</span>
              </div>
            ) : pageError ? (
              <div className="p-4 rounded border border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-300 text-xs">
                {pageError}
              </div>
            ) : pageData ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between pb-2 border-b border-border-hairline text-xs font-mono text-ink-muted">
                  <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                    <ShieldCheck className="w-3.5 h-3.5" /> Verified Ground Truth Text
                  </span>
                  <span>{pageData.text.length} characters</span>
                </div>
                {renderHighlightedContent(pageData.text)}
              </div>
            ) : null}
          </div>
        ) : (
          <div className="w-full h-full min-h-[450px] rounded border border-border-hairline overflow-hidden bg-white">
            <iframe
              src={`${pdfUrl}#page=${currentPage}&toolbar=1&navpanes=0`}
              title={`${paper.title} PDF`}
              className="w-full h-full min-h-[450px]"
            />
          </div>
        )}
      </div>

      {/* Footer Info */}
      <div className="p-3 border-t border-border-hairline bg-paper-bg/60 text-[11px] text-ink-muted flex items-center justify-between font-mono">
        <span>License: {paper.license}</span>
        <Badge variant="verified">Public Demo Corpus</Badge>
      </div>
    </div>
  );
};

