import React, { useState, useEffect } from 'react';
import { X, FileText, AlertTriangle, Layers, BookOpen, ChevronLeft, ChevronRight, Loader2, Download, Image as ImageIcon } from 'lucide-react';
import { DocumentItem } from '../../types';
import { api } from '../../services/api';
import { StatusBadge } from '../../components/common/StatusBadge';
import { getPaperInk, getPaperInitial } from '../../utils/paperInks';

export interface DocumentDetailModalProps {
  document: DocumentItem | null;
  initialPage?: number;
  onClose: () => void;
}

export const DocumentDetailModal: React.FC<DocumentDetailModalProps> = ({
  document,
  initialPage = 1,
  onClose,
}) => {
  const [activePage, setActivePage] = useState<number>(initialPage || 1);
  const [pageContent, setPageContent] = useState<string>('');
  const [isLoadingPage, setIsLoadingPage] = useState<boolean>(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const [modalViewMode, setModalViewMode] = useState<'canvas' | 'text'>('canvas');
  const [isCanvasLoading, setIsCanvasLoading] = useState<boolean>(true);
  const [canvasError, setCanvasError] = useState<string | null>(null);

  useEffect(() => {
    if (initialPage && initialPage > 0) {
      setActivePage(initialPage);
    }
  }, [initialPage, document]);

  useEffect(() => {
    if (document && document.status === 'completed' && document.page_count > 0) {
      loadPage(activePage);
    }
  }, [document, activePage]);

  useEffect(() => {
    if (!document) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [document, onClose]);

  if (!document) return null;

  const ink = getPaperInk(document.filename || document.id);
  const initial = getPaperInitial(document.filename);

  const loadPage = async (pageNumber: number) => {
    setActivePage(pageNumber);
    setIsLoadingPage(true);
    setPageError(null);
    setIsCanvasLoading(true);
    setCanvasError(null);
    try {
      const data = await api.getDocumentPage(document.id, pageNumber);
      setPageContent(data.text);
      setIsLoadingPage(false);
    } catch (err: any) {
      setPageError(err.message || 'Failed to fetch page text.');
      setIsLoadingPage(false);
    }
  };

  const pdfFileUrl = api.getDocumentFileUrl(document.id);
  const pageRenderUrl = api.getDocumentPageRenderUrl(document.id, activePage, 150);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-3 sm:p-4 font-sans">
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Document details for ${document.filename}`}
        className="bg-paper-surface rounded-xl shadow-paper-elevated border border-border-hairline max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150"
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 sm:px-6 py-3 sm:py-4 border-b border-border-hairline bg-paper-surface shrink-0"
          style={{ borderTop: `3px solid ${ink.hex}` }}
        >
          <div className="flex items-center gap-3 min-w-0">
            <span
              className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold text-white shrink-0 shadow-xs"
              style={{ backgroundColor: ink.hex }}
            >
              {initial}
            </span>
            <div className="min-w-0">
              <h2 className="text-xs sm:text-sm font-semibold text-ink truncate max-w-xs sm:max-w-md">
                {document.filename}
              </h2>
              <div className="flex items-center gap-2 mt-0.5">
                <StatusBadge status={document.status} />
                <span className="text-[10px] sm:text-xs font-mono text-ink-muted truncate">
                  ID: {document.id}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <a
              href={pdfFileUrl}
              target="_blank"
              rel="noopener noreferrer"
              download={document.filename}
              className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-lg border border-border-hairline bg-paper-card text-ink hover:bg-paper-bg transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Download PDF</span>
            </a>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close document details"
              className="p-1 rounded-md text-ink-muted hover:text-ink hover:bg-paper-raised transition-colors shrink-0"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="p-4 sm:p-6 overflow-y-auto space-y-4 sm:space-y-5 flex-1 min-h-0 bg-paper-bg">
          {/* Metadata Cards Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3 text-xs">
            <div className="p-3 bg-paper-card rounded-lg border border-border-hairline shadow-subtle">
              <span className="text-ink-muted block mb-1">File Size</span>
              <span className="font-mono font-semibold text-ink">
                {(document.file_size / (1024 * 1024)).toFixed(2)} MB
              </span>
            </div>
            <div className="p-3 bg-paper-card rounded-lg border border-border-hairline shadow-subtle">
              <span className="text-ink-muted block mb-1">Total Pages</span>
              <span className="font-mono font-semibold text-ink">
                {document.page_count} pages
              </span>
            </div>
            <div className="p-3 bg-paper-card rounded-lg border border-border-hairline shadow-subtle">
              <span className="text-ink-muted block mb-1">Indexed Chunks</span>
              <span className="font-mono font-semibold text-ink">
                {document.chunk_count} chunks
              </span>
            </div>
            <div className="p-3 bg-paper-card rounded-lg border border-border-hairline shadow-subtle">
              <span className="text-ink-muted block mb-1">Uploaded</span>
              <span className="font-mono text-ink">
                {new Date(document.created_at).toLocaleDateString()}
              </span>
            </div>
          </div>

          {/* Extraction Warnings */}
          {document.extraction_warnings && document.extraction_warnings.length > 0 && (
            <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg text-amber-800 dark:text-amber-300 text-xs space-y-1">
              <div className="flex items-center gap-2 font-semibold">
                <AlertTriangle className="w-4 h-4 text-amber-600" />
                <span>Extraction Warnings</span>
              </div>
              <ul className="list-disc pl-5 space-y-0.5">
                {document.extraction_warnings.map((w, idx) => (
                  <li key={idx}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Processing Error if failed */}
          {document.processing_error && (
            <div className="p-3.5 bg-amber-500/10 border border-amber-500/30 rounded-lg text-ink-900 text-xs flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold text-amber-900 dark:text-amber-300 mb-0.5">Ingestion Unsuccessful</div>
                <p className="text-ink-700 dark:text-ink-muted leading-relaxed">{document.processing_error}</p>
              </div>
            </div>
          )}

          {/* Page Inspector with Provenance */}
          {document.status === 'completed' && document.page_count > 0 && (
            <div className="border border-border-hairline rounded-lg overflow-hidden bg-paper-card shadow-subtle">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between px-4 py-2.5 bg-paper-surface border-b border-border-hairline gap-2">
                <div className="flex items-center gap-2 text-xs font-semibold text-ink">
                  <BookOpen className="w-4 h-4 text-reading-primary" />
                  <span>Page Provenance & Canvas</span>
                </div>

                {/* View toggles & Pagination */}
                <div className="flex items-center justify-between sm:justify-end gap-3">
                  <div className="flex items-center bg-paper-bg p-0.5 rounded border border-border-hairline text-xs">
                    <button
                      type="button"
                      onClick={() => setModalViewMode('canvas')}
                      className={`px-2 py-0.5 rounded transition-all ${
                        modalViewMode === 'canvas'
                          ? 'bg-paper-surface text-ink font-semibold shadow-xs'
                          : 'text-ink-muted hover:text-ink'
                      }`}
                    >
                      PDF Page Canvas
                    </button>
                    <button
                      type="button"
                      onClick={() => setModalViewMode('text')}
                      className={`px-2 py-0.5 rounded transition-all ${
                        modalViewMode === 'text'
                          ? 'bg-paper-surface text-ink font-semibold shadow-xs'
                          : 'text-ink-muted hover:text-ink'
                      }`}
                    >
                      Extracted Text
                    </button>
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      disabled={activePage <= 1 || isLoadingPage}
                      onClick={() => loadPage(activePage - 1)}
                      className="p-1 rounded hover:bg-paper-raised disabled:opacity-40 text-ink-muted hover:text-ink"
                      aria-label="Previous page"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <span className="text-xs font-mono text-ink">
                      Page {activePage} of {document.page_count}
                    </span>
                    <button
                      type="button"
                      disabled={activePage >= document.page_count || isLoadingPage}
                      onClick={() => loadPage(activePage + 1)}
                      className="p-1 rounded hover:bg-paper-raised disabled:opacity-40 text-ink-muted hover:text-ink"
                      aria-label="Next page"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>

              {/* View Content */}
              <div className="p-4 bg-paper-bg min-h-[300px] max-h-[440px] overflow-y-auto flex flex-col items-center justify-center">
                {modalViewMode === 'canvas' ? (
                  <div className="relative max-w-lg w-full flex flex-col items-center">
                    {isCanvasLoading && (
                      <div className="py-12 flex flex-col items-center justify-center gap-2">
                        <Loader2 className="w-6 h-6 animate-spin text-reading-primary" />
                        <span className="text-xs font-mono text-ink-muted">Rendering page {activePage}...</span>
                      </div>
                    )}
                    {canvasError ? (
                      <div className="p-4 text-center text-xs text-amber-600">
                        {canvasError}
                        <button
                          type="button"
                          onClick={() => setModalViewMode('text')}
                          className="mt-2 block mx-auto underline"
                        >
                          Switch to Extracted Text
                        </button>
                      </div>
                    ) : (
                      <img
                        src={pageRenderUrl}
                        alt={`Page ${activePage} of ${document.filename}`}
                        onLoad={() => setIsCanvasLoading(false)}
                        onError={() => {
                          setIsCanvasLoading(false);
                          setCanvasError('Could not render page canvas.');
                        }}
                        className={`rounded border border-border-hairline shadow-paper max-h-[400px] w-auto ${
                          isCanvasLoading ? 'hidden' : 'block'
                        }`}
                      />
                    )}
                  </div>
                ) : (
                  <div className="w-full text-xs leading-relaxed font-serif text-ink whitespace-pre-wrap select-text">
                    {isLoadingPage ? (
                      <div className="flex items-center justify-center h-32 gap-2 text-ink-muted">
                        <Loader2 className="w-5 h-5 animate-spin" />
                        <span>Loading page text...</span>
                      </div>
                    ) : pageError ? (
                      <div className="text-red-700">{pageError}</div>
                    ) : (
                      pageContent || 'No text extracted on this page.'
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-border-hairline bg-paper-surface flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-ink bg-paper-card hover:bg-paper-raised border border-border-hairline rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
