import React, { useState, useEffect, useCallback } from 'react';
import {
  FileText,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Download,
  AlertTriangle,
  ShieldCheck,
  RotateCcw,
  BookOpen,
  Loader2,
  ExternalLink,
  Layers,
  Sparkles,
} from 'lucide-react';
import { CitationItem, DocumentItem } from '../../types';
import { api } from '../../services/api';
import { getPaperInk, getPaperInitial } from '../../utils/paperInks';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';

export interface PdfEvidenceViewerProps {
  documentId?: string;
  filename?: string;
  pageNumber?: number;
  excerpt?: string;
  citationId?: number | string;
  chunkIds?: string[];
  allCitations?: CitationItem[];
  currentCitationIndex?: number;
  onNavigateCitation?: (direction: 'prev' | 'next') => void;
  onSelectCitation?: (citation: CitationItem) => void;
  onClose?: () => void;
  onOpenFullDocument?: (docId: string, pageNumber?: number) => void;
  isDrawer?: boolean;
}

export type ViewMode = 'rendered' | 'interactive' | 'extracted';

export const PdfEvidenceViewer: React.FC<PdfEvidenceViewerProps> = ({
  documentId,
  filename = 'Research Publication.pdf',
  pageNumber = 1,
  excerpt,
  citationId,
  chunkIds = [],
  allCitations = [],
  currentCitationIndex = 0,
  onNavigateCitation,
  onSelectCitation,
  onClose,
  onOpenFullDocument,
  isDrawer = false,
}) => {
  const [currentPage, setCurrentPage] = useState<number>(pageNumber || 1);
  const [totalPages, setTotalPages] = useState<number | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('rendered');
  const [zoomLevel, setZoomLevel] = useState<number>(100); // 75, 100, 125, 150

  // Page image state
  const [isImageLoading, setIsImageLoading] = useState<boolean>(true);
  const [imageError, setImageError] = useState<string | null>(null);

  // Extracted text state
  const [extractedText, setExtractedText] = useState<string | null>(null);
  const [isTextLoading, setIsTextLoading] = useState<boolean>(false);
  const [textError, setTextError] = useState<string | null>(null);
  const [textCharCount, setTextCharCount] = useState<number>(0);

  const ink = getPaperInk(filename || documentId || 'paper');
  const initial = getPaperInitial(filename);

  // Sync currentPage whenever cited pageNumber changes
  useEffect(() => {
    if (pageNumber && pageNumber > 0) {
      setCurrentPage(pageNumber);
    }
  }, [pageNumber, documentId]);

  // Load document metadata to find total pages
  useEffect(() => {
    if (!documentId) return;
    let isMounted = true;
    api
      .getDocument(documentId)
      .then((doc) => {
        if (isMounted && doc?.page_count) {
          setTotalPages(doc.page_count);
        }
      })
      .catch((err) => {
        console.warn('Could not load document page count:', err);
      });
    return () => {
      isMounted = false;
    };
  }, [documentId]);

  // Load extracted page text when extracted view mode is active
  const loadExtractedText = useCallback(
    async (page: number) => {
      if (!documentId) return;
      setIsTextLoading(true);
      setTextError(null);
      try {
        const res = await api.getDocumentPage(documentId, page);
        setExtractedText(res.text);
        setTextCharCount(res.character_count);
        setIsTextLoading(false);
      } catch (err: any) {
        setTextError(err?.message || 'Failed to retrieve page text from document.');
        setIsTextLoading(false);
      }
    },
    [documentId]
  );

  useEffect(() => {
    if (viewMode === 'extracted' && documentId) {
      loadExtractedText(currentPage);
    }
  }, [viewMode, currentPage, documentId, loadExtractedText]);

  // Reset image loading when changing page or doc
  useEffect(() => {
    setIsImageLoading(true);
    setImageError(null);
  }, [currentPage, documentId]);

  // Keyboard navigation shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if user is typing in an input or textarea
      const target = e.target as HTMLElement;
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable
      ) {
        return;
      }

      // [ for previous citation, ] for next citation
      if (e.key === '[' && onNavigateCitation) {
        e.preventDefault();
        onNavigateCitation('prev');
      } else if (e.key === ']' && onNavigateCitation) {
        e.preventDefault();
        onNavigateCitation('next');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onNavigateCitation]);

  // Page navigation handlers
  const handlePrevPage = () => {
    if (currentPage > 1) {
      setCurrentPage((p) => p - 1);
    }
  };

  const handleNextPage = () => {
    if (!totalPages || currentPage < totalPages) {
      setCurrentPage((p) => p + 1);
    }
  };

  const handleZoomIn = () => {
    setZoomLevel((z) => Math.min(z + 25, 200));
  };

  const handleZoomOut = () => {
    setZoomLevel((z) => Math.max(z - 25, 60));
  };

  const handleResetZoom = () => {
    setZoomLevel(100);
  };

  // If no document is selected
  if (!documentId) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-6 text-center space-y-3 bg-paper-surface">
        <div className="w-12 h-12 rounded-full bg-paper-bg border border-border-hairline flex items-center justify-center text-ink-muted">
          <BookOpen className="w-5 h-5 opacity-60" />
        </div>
        <div className="font-serif text-sm font-medium text-ink">
          No Citation Selected
        </div>
        <p className="max-w-[260px] leading-relaxed font-sans text-xs text-ink-secondary">
          Click any numbered citation chip in an answer to inspect its original PDF page and verified passage.
        </p>
      </div>
    );
  }

  const isInvalidPage = totalPages !== null && (currentPage < 1 || currentPage > totalPages);
  const pdfFileUrl = api.getDocumentFileUrl(documentId);
  const pageRenderUrl = api.getDocumentPageRenderUrl(documentId, currentPage, 150);

  return (
    <div
      className="flex flex-col h-full min-w-0 bg-paper-surface select-none font-sans"
      data-testid="pdf-evidence-viewer"
    >
      {/* 1. Top Provenance & Document Header */}
      <div
        className="p-3 border-b border-border-hairline bg-paper-surface flex flex-col gap-2 shrink-0"
        style={{ borderTop: `3px solid ${ink.hex}` }}
      >
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-mono uppercase tracking-wider text-ink-muted">
            Citation Provenance Target
          </span>
          <Badge variant="verified" size="sm" className="hidden sm:inline-flex">
            <ShieldCheck className="w-3 h-3 mr-1" />
            Verified Provenance
          </Badge>
        </div>

        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <span
              className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white shrink-0 shadow-xs"
              style={{ backgroundColor: ink.hex }}
              title={filename}
            >
              {initial}
            </span>
            <span
              className="text-xs font-serif font-bold text-ink truncate max-w-[190px] sm:max-w-[260px]"
              title={filename}
            >
              {filename}
            </span>
          </div>

          <div className="flex items-center gap-1 shrink-0">

            {onOpenFullDocument && (
              <button
                type="button"
                onClick={() => onOpenFullDocument(documentId, currentPage)}
                title="Open Document Metadata Modal"
                className="p-1 rounded text-ink-muted hover:text-ink hover:bg-paper-raised transition-colors"
                aria-label="Open Document Details Modal"
              >
                <Maximize2 className="w-3.5 h-3.5" />
              </button>
            )}

            <a
              href={pdfFileUrl}
              target="_blank"
              rel="noopener noreferrer"
              download={filename}
              title="Download Original PDF"
              className="p-1 rounded text-ink-muted hover:text-ink hover:bg-paper-raised transition-colors"
              aria-label="Download original PDF"
            >
              <Download className="w-3.5 h-3.5" />
            </a>
          </div>
        </div>

        {/* View Mode Switcher Pills */}
        <div className="flex items-center justify-between gap-2 pt-1 border-t border-border-subtle">
          <div className="flex items-center gap-1 bg-paper-bg p-0.5 rounded-lg border border-border-hairline text-[11px] font-medium">
            <button
              type="button"
              onClick={() => setViewMode('rendered')}
              className={`px-2 py-0.5 rounded-md transition-all ${
                viewMode === 'rendered'
                  ? 'bg-paper-surface text-ink shadow-xs font-semibold'
                  : 'text-ink-muted hover:text-ink'
              }`}
            >
              PDF Page
            </button>
            <button
              type="button"
              onClick={() => setViewMode('interactive')}
              className={`px-2 py-0.5 rounded-md transition-all ${
                viewMode === 'interactive'
                  ? 'bg-paper-surface text-ink shadow-xs font-semibold'
                  : 'text-ink-muted hover:text-ink'
              }`}
            >
              Interactive PDF
            </button>
            <button
              type="button"
              onClick={() => setViewMode('extracted')}
              className={`px-2 py-0.5 rounded-md transition-all ${
                viewMode === 'extracted'
                  ? 'bg-paper-surface text-ink shadow-xs font-semibold'
                  : 'text-ink-muted hover:text-ink'
              }`}
            >
              Extracted Text
            </button>
          </div>

          <span className="text-[11px] font-mono text-ink-muted">
            Page {currentPage} {totalPages ? `of ${totalPages}` : ''}
          </span>
        </div>
      </div>

      {/* 2. Citation Navigation Bar (When answer has multiple citations) */}
      {allCitations && allCitations.length > 1 && onNavigateCitation && (
        <div
          className="px-3 py-1.5 bg-paper-raised border-b border-border-hairline flex items-center justify-between text-xs"
          data-testid="citation-navigation-bar"
        >
          <div className="flex items-center gap-1.5 text-[11px] font-mono text-ink-secondary">
            <Sparkles className="w-3.5 h-3.5 text-reading-primary shrink-0" />
            <span>
              Citation <strong className="text-ink">{currentCitationIndex + 1}</strong> of{' '}
              <strong className="text-ink">{allCitations.length}</strong>
            </span>
            <span className="hidden sm:inline text-ink-muted text-[10px]">
              (Keys: <kbd className="px-1 py-0.5 bg-paper-surface rounded border border-border-hairline font-mono">[</kbd> / <kbd className="px-1 py-0.5 bg-paper-surface rounded border border-border-hairline font-mono">]</kbd>)
            </span>
          </div>

          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => onNavigateCitation('prev')}
              disabled={currentCitationIndex <= 0}
              aria-label="Previous citation"
              className="px-2 py-0.5 rounded text-[11px] font-medium border border-border-hairline bg-paper-surface text-ink disabled:opacity-40 disabled:cursor-not-allowed hover:bg-paper-bg transition-colors"
            >
              &larr; Prev
            </button>
            <button
              type="button"
              onClick={() => onNavigateCitation('next')}
              disabled={currentCitationIndex >= allCitations.length - 1}
              aria-label="Next citation"
              className="px-2 py-0.5 rounded text-[11px] font-medium border border-border-hairline bg-paper-surface text-ink disabled:opacity-40 disabled:cursor-not-allowed hover:bg-paper-bg transition-colors"
            >
              Next &rarr;
            </button>
          </div>
        </div>
      )}

      {/* 3. Supporting Passage Excerpt Callout */}
      {excerpt && (
        <div className="p-3 border-b border-border-hairline bg-paper-bg shrink-0 space-y-1">
          <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-ink-muted">
            <span className="flex items-center gap-1 font-semibold text-reading-primary">
              <FileText className="w-3 h-3" />
              Supporting Passage Excerpt (p. {pageNumber})
            </span>
            {citationId && <span>Citation [{citationId}]</span>}
          </div>
          <div
            className="p-2.5 rounded bg-paper-surface border text-xs leading-relaxed font-serif text-ink italic shadow-xs"
            style={{
              borderColor: ink.borderLight,
              borderLeftWidth: '3.5px',
              borderLeftColor: ink.hex,
            }}
          >
            "{excerpt}"
          </div>
          <p className="text-[10px] font-mono text-ink-muted pt-0.5">
            Exact text coordinate bounding-box is not stored by document pipeline &mdash; showing verified source page.
          </p>
        </div>
      )}

      {/* 4. Page Navigation & Zoom Toolbar (Active for Rendered and Extracted modes) */}
      <div className="px-3 py-1.5 border-b border-border-hairline bg-paper-surface flex items-center justify-between text-xs shrink-0">
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={handlePrevPage}
            disabled={currentPage <= 1}
            aria-label="Previous page"
            className="p-1 rounded text-ink-muted hover:text-ink hover:bg-paper-raised disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          <span className="text-[11px] font-mono text-ink font-medium px-1">
            Page {currentPage} {totalPages ? `/ ${totalPages}` : ''}
          </span>

          <button
            type="button"
            onClick={handleNextPage}
            disabled={Boolean(totalPages && currentPage >= totalPages)}
            aria-label="Next page"
            className="p-1 rounded text-ink-muted hover:text-ink hover:bg-paper-raised disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {/* Zoom controls for Rendered mode */}
        {viewMode === 'rendered' && (
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={handleZoomOut}
              disabled={zoomLevel <= 60}
              aria-label="Zoom out"
              className="p-1 rounded text-ink-muted hover:text-ink hover:bg-paper-raised disabled:opacity-30 transition-colors"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <span
              className="text-[10px] font-mono text-ink-muted cursor-pointer hover:text-ink px-1"
              onClick={handleResetZoom}
              title="Click to reset zoom"
            >
              {zoomLevel}%
            </span>
            <button
              type="button"
              onClick={handleZoomIn}
              disabled={zoomLevel >= 200}
              aria-label="Zoom in"
              className="p-1 rounded text-ink-muted hover:text-ink hover:bg-paper-raised disabled:opacity-30 transition-colors"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* 5. Main Canvas / Viewer Content Area */}
      <div className="flex-1 overflow-auto bg-paper-bg relative flex flex-col items-center justify-start p-3 min-h-0">
        {/* Out-of-bounds Page Error */}
        {isInvalidPage && (
          <div className="w-full max-w-md p-4 bg-paper-card border border-amber-300 rounded-lg shadow-subtle space-y-2 text-center my-auto">
            <AlertTriangle className="w-6 h-6 text-amber-600 mx-auto" />
            <div className="font-serif font-bold text-ink text-sm">
              Invalid Page Number
            </div>
            <p className="text-xs text-ink-secondary">
              Page {currentPage} is outside the document boundaries (1 to {totalPages}).
            </p>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setCurrentPage(1)}
              className="mx-auto text-xs"
            >
              Jump to Page 1
            </Button>
          </div>
        )}

        {/* VIEW MODE 1: Rendered Crisp Page Image */}
        {!isInvalidPage && viewMode === 'rendered' && (
          <div className="relative w-full flex flex-col items-center justify-start min-h-full">
            {isImageLoading && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-paper-bg/80 backdrop-blur-xs z-10 py-12">
                <Loader2 className="w-6 h-6 animate-spin text-reading-primary" />
                <span className="text-xs font-mono text-ink-muted">
                  Rendering PDF Page {currentPage}...
                </span>
              </div>
            )}

            {imageError ? (
              <div className="w-full max-w-md p-5 bg-paper-card border border-border-hairline rounded-lg shadow-subtle space-y-3 text-center my-auto">
                <AlertTriangle className="w-6 h-6 text-amber-600 mx-auto" />
                <div className="font-serif font-bold text-ink text-sm">
                  PDF Page Render Unavailable
                </div>
                <p className="text-xs text-ink-secondary leading-relaxed">
                  The visual canvas for page {currentPage} could not be rendered from storage. You can view the extracted plain text or open the interactive PDF.
                </p>
                <div className="flex justify-center gap-2 pt-2">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => setViewMode('extracted')}
                    className="text-xs"
                  >
                    View Extracted Text
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      setIsImageLoading(true);
                      setImageError(null);
                    }}
                    className="text-xs gap-1"
                  >
                    <RotateCcw className="w-3 h-3" />
                    Retry
                  </Button>
                </div>
              </div>
            ) : (
              <div
                className="transition-transform duration-100 ease-out shadow-paper-elevated border border-border-hairline rounded bg-white overflow-hidden"
                style={{
                  width: `${zoomLevel}%`,
                  maxWidth: '100%',
                }}
              >
                <img
                  src={pageRenderUrl}
                  alt={`Page ${currentPage} of ${filename}`}
                  onLoad={() => setIsImageLoading(false)}
                  onError={() => {
                    setIsImageLoading(false);
                    setImageError('Failed to load page render.');
                  }}
                  className="w-full h-auto block select-text"
                  loading="lazy"
                />
              </div>
            )}
          </div>
        )}

        {/* VIEW MODE 2: Interactive Embedded PDF Viewer */}
        {!isInvalidPage && viewMode === 'interactive' && (
          <div className="w-full h-full flex flex-col rounded-lg border border-border-hairline overflow-hidden bg-white shadow-paper">
            <iframe
              src={`${pdfFileUrl}#page=${currentPage}&view=FitH`}
              title={`Interactive PDF viewer for ${filename}`}
              className="w-full flex-1 border-0"
            />
          </div>
        )}

        {/* VIEW MODE 3: Extracted Text & Chunk Inspector (Fallback) */}
        {!isInvalidPage && viewMode === 'extracted' && (
          <div className="w-full max-w-2xl bg-paper-card border border-border-hairline rounded-lg shadow-subtle p-4 space-y-4">
            <div className="flex items-center justify-between border-b border-border-subtle pb-2">
              <span className="text-xs font-mono font-semibold uppercase tracking-wider text-ink-muted">
                Extracted Page Plain Text &bull; p. {currentPage}
              </span>
              <span className="text-[11px] font-mono text-ink-muted">
                {textCharCount.toLocaleString()} chars
              </span>
            </div>

            {isTextLoading ? (
              <div className="py-12 flex flex-col items-center justify-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin text-reading-primary" />
                <span className="text-xs font-mono text-ink-muted">
                  Fetching extracted page text...
                </span>
              </div>
            ) : textError ? (
              <div className="p-3 bg-red-50 text-red-700 text-xs rounded border border-red-200">
                {textError}
              </div>
            ) : (
              <div className="font-serif text-sm leading-relaxed text-ink whitespace-pre-wrap selection:bg-highlight-bg">
                {extractedText || 'No text extracted on this page.'}
              </div>
            )}

            {/* Chunk IDs attribution */}
            {chunkIds.length > 0 && (
              <div className="pt-2 border-t border-border-subtle text-[11px] font-mono text-ink-muted flex items-start gap-1">
                <Layers className="w-3.5 h-3.5 text-reading-primary shrink-0 mt-0.5" />
                <span>Indexed Chunk IDs: {chunkIds.join(', ')}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
