import React, { Suspense, lazy } from 'react';
import { BookOpen, ExternalLink, X, ShieldCheck, FileText, ChevronLeft, ChevronRight, Eye, Layers } from 'lucide-react';
import { CitationItem } from '../../types';
import { getPaperInk, getPaperInitial } from '../../utils/paperInks';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';

import { PdfEvidenceViewer } from './PdfEvidenceViewer';

export interface EvidenceInspectorProps {
  activeCitation: CitationItem | null;
  allCitations?: CitationItem[];
  onSelectCitation?: (citation: CitationItem) => void;
  onClearCitation: () => void;
  onOpenDocument: (documentId: string, pageNumber?: number) => void;
  onCloseDrawer?: () => void;
  isDrawer?: boolean;
}

export const EvidenceInspector: React.FC<EvidenceInspectorProps> = ({
  activeCitation,
  allCitations = [],
  onSelectCitation,
  onClearCitation,
  onOpenDocument,
  onCloseDrawer,
  isDrawer = false,
}) => {
  const [activeTab, setActiveTab] = React.useState<'pdf' | 'metadata'>('pdf');

  const ink = activeCitation
    ? getPaperInk(activeCitation.filename || activeCitation.document_id)
    : null;
  const initial = activeCitation
    ? getPaperInitial(activeCitation.filename)
    : 'P';

  // Find index of active citation in all citations list
  const currentCitationIndex = React.useMemo(() => {
    if (!activeCitation || allCitations.length === 0) return 0;
    const idx = allCitations.findIndex(
      (c) => c.citation_id === activeCitation.citation_id && c.document_id === activeCitation.document_id
    );
    return idx >= 0 ? idx : 0;
  }, [activeCitation, allCitations]);

  const handleNavigateCitation = (direction: 'prev' | 'next') => {
    if (!allCitations || allCitations.length === 0 || !onSelectCitation) return;
    if (direction === 'prev' && currentCitationIndex > 0) {
      onSelectCitation(allCitations[currentCitationIndex - 1]);
    } else if (direction === 'next' && currentCitationIndex < allCitations.length - 1) {
      onSelectCitation(allCitations[currentCitationIndex + 1]);
    }
  };

  return (
    <div className="flex flex-col h-full min-w-0 bg-paper-surface select-none font-sans">
      {/* Top Inspector Title Header */}
      <div className="p-3 border-b border-border-hairline bg-paper-surface flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-reading-primary shrink-0" />
          <span className="text-xs font-semibold uppercase tracking-wider text-ink font-mono">
            Evidence Inspector
          </span>
          {activeCitation && (
            <Badge variant="verified" size="sm">
              <ShieldCheck className="w-3 h-3 mr-1" />
              Verified
            </Badge>
          )}
        </div>

        <div className="flex items-center gap-1">
          {activeCitation && (
            <div className="flex items-center bg-paper-bg p-0.5 rounded border border-border-hairline text-[10px] mr-1">
              <button
                type="button"
                onClick={() => setActiveTab('pdf')}
                className={`px-1.5 py-0.5 rounded transition-all ${
                  activeTab === 'pdf'
                    ? 'bg-paper-surface text-ink font-semibold shadow-xs'
                    : 'text-ink-muted hover:text-ink'
                }`}
                title="View PDF Evidence Canvas"
              >
                PDF View
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('metadata')}
                className={`px-1.5 py-0.5 rounded transition-all ${
                  activeTab === 'metadata'
                    ? 'bg-paper-surface text-ink font-semibold shadow-xs'
                    : 'text-ink-muted hover:text-ink'
                }`}
                title="View Chunk Metadata"
              >
                Metadata
              </button>
            </div>
          )}

          <button
            type="button"
            onClick={() => {
              if (onCloseDrawer) {
                onCloseDrawer();
              } else if (onClearCitation) {
                onClearCitation();
              }
            }}
            aria-label="Close Evidence Inspector"
            title="Close Evidence Inspector"
            className="p-1.5 rounded-lg text-ink-muted hover:text-ink hover:bg-paper-raised transition-colors ml-1 focus:outline-none focus:ring-1 focus:ring-reading-primary"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Content: Either PDF Viewer (Default) or Metadata/Chunk Fallback */}
      <div className="flex-1 min-h-0 flex flex-col">
        {activeCitation ? (
          activeTab === 'pdf' ? (
            <PdfEvidenceViewer
              documentId={activeCitation.document_id}
              filename={activeCitation.filename}
              pageNumber={activeCitation.page_numbers[0] || 1}
              excerpt={activeCitation.excerpt}
              citationId={activeCitation.citation_id}
              chunkIds={activeCitation.chunk_ids}
              allCitations={allCitations}
              currentCitationIndex={currentCitationIndex}
              onNavigateCitation={handleNavigateCitation}
              onSelectCitation={onSelectCitation}
              onOpenFullDocument={onOpenDocument}
              isDrawer={isDrawer}
            />
          ) : (
            /* Tab: Metadata / Chunk Inspector Fallback */
            <div className="p-4 sm:p-5 overflow-y-auto flex-1 space-y-4 font-sans animate-in fade-in-0 duration-150">
              {/* Target Document Card */}
              <div
                className="p-3.5 rounded-lg border bg-paper-card shadow-subtle space-y-1.5"
                style={{ borderColor: ink?.borderLight }}
              >
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-ink-muted">
                    Citation Provenance Target
                  </span>
                  <span
                    className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white shadow-xs"
                    style={{ backgroundColor: ink?.hex }}
                  >
                    {initial}
                  </span>
                </div>

                <div className="text-sm font-serif font-bold text-ink truncate leading-tight">
                  {activeCitation.filename}
                </div>

                <div className="flex items-center gap-2 text-xs font-mono text-ink-secondary pt-0.5">
                  <span className="font-semibold text-ink">
                    Page {activeCitation.page_numbers.join(', ')}
                  </span>
                  <span>&bull;</span>
                  <span className="text-ink-muted">Citation [{activeCitation.citation_id}]</span>
                </div>
              </div>

              {/* Retrieved Excerpt */}
              <div className="space-y-2">
                <div className="text-xs font-mono uppercase tracking-wider text-ink-muted font-medium flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-reading-primary" />
                  <span>Supporting Passage Excerpt</span>
                </div>

                <div
                  className="p-4 rounded-lg bg-paper-bg border text-xs sm:text-sm leading-relaxed font-serif text-ink shadow-inner break-words relative overflow-hidden"
                  style={{
                    borderColor: ink?.borderLight,
                    borderLeftWidth: '4px',
                    borderLeftColor: ink?.hex,
                  }}
                >
                  "{activeCitation.excerpt}"
                </div>
              </div>

              {/* Provenance Metadata Table */}
              <div className="p-3 rounded-lg bg-paper-card border border-border-hairline text-[11px] font-mono text-ink-secondary space-y-1.5">
                <div className="flex justify-between items-center pb-1 border-b border-border-subtle">
                  <span className="text-ink-muted">Citation Identifier:</span>
                  <span className="font-semibold text-ink">[{activeCitation.citation_id}]</span>
                </div>
                <div className="flex justify-between items-center pb-1 border-b border-border-subtle">
                  <span className="text-ink-muted">Document ID:</span>
                  <span className="truncate max-w-[180px] text-ink">{activeCitation.document_id}</span>
                </div>
                <div className="flex justify-between items-start pt-0.5">
                  <span className="text-ink-muted shrink-0 mr-2">Matched Chunks:</span>
                  <span className="break-all text-right text-ink font-mono text-[10px]">
                    {activeCitation.chunk_ids.join(', ')}
                  </span>
                </div>
              </div>

              {/* Switch back to PDF button */}
              <Button
                variant="primary"
                onClick={() => setActiveTab('pdf')}
                className="w-full text-xs gap-1.5"
              >
                <Eye className="w-3.5 h-3.5" />
                <span>Switch to PDF Page Canvas</span>
              </Button>

              {/* Inspect Full Document Button */}
              <Button
                variant="secondary"
                onClick={() => onOpenDocument(activeCitation.document_id, activeCitation.page_numbers[0] || 1)}
                className="w-full text-xs gap-1.5"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                <span>Open Full Document Details Modal</span>
              </Button>
            </div>
          )
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 text-xs text-ink-muted space-y-3">
            <div className="w-12 h-12 rounded-full bg-paper-bg border border-border-hairline flex items-center justify-center text-ink-muted">
              <BookOpen className="w-5 h-5 opacity-60" />
            </div>
            <div className="font-serif text-sm font-medium text-ink">
              No citation selected
            </div>
            <p className="max-w-[240px] leading-relaxed font-sans text-[11px] text-ink-secondary">
              Click any numbered citation chip in an answer to inspect its original document provenance and verified PDF passage.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
