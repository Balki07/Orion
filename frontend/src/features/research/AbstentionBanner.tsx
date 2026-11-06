import React from 'react';
import { Compass, BookOpen, Layers, RefreshCw, AlertCircle } from 'lucide-react';

export interface AbstentionBannerProps {
  insufficientEvidence?: boolean;
  reasonCode?: string;
  traceId?: string;
  onOpenSources?: () => void;
}

export const AbstentionBanner: React.FC<AbstentionBannerProps> = ({
  insufficientEvidence,
  reasonCode,
  traceId,
  onOpenSources,
}) => {
  if (!insufficientEvidence) return null;

  const getReasonDetails = (code?: string) => {
    switch (code) {
      case 'NO_SELECTED_DOCUMENTS':
        return {
          title: 'No Documents Selected in Active Scope',
          description:
            'The inquiry cannot be evaluated because no papers are currently selected. Please select one or more research publications in the Sources panel.',
          suggestion: 'Select at least one indexed paper from the left panel to begin retrieval.',
        };
      case 'SELECTED_DOCUMENTS_NOT_INDEXED':
        return {
          title: 'Document Indexing in Progress',
          description:
            'The selected publications are still being processed or chunked. Evidence retrieval will be enabled once indexing completes.',
          suggestion: 'Check processing status in the Document Library or wait for completion.',
        };
      case 'RETRIEVAL_NO_CANDIDATES':
        return {
          title: 'Concept Not Found in Selected Literature',
          description:
            'No passages matching this inquiry were identified across the active documents. The requested topic may be outside the scope of the selected papers.',
          suggestion: 'Try expanding your scope to all indexed papers, or rephrasing with specific technical or statutory terms.',
        };
      case 'CANDIDATES_REJECTED_BY_FILTER':
        return {
          title: 'Passages Below Evidentiary Threshold',
          description:
            'Passages were retrieved, but their semantic relevance score fell below ORION’s verification threshold for authoritative synthesis.',
          suggestion: 'Narrow the inquiry to a specific section, table, or finding reported in the paper.',
        };
      case 'CITATION_VALIDATION_FAILED':
        return {
          title: 'Citation Provenance Safeguard Triggered',
          description:
            'Candidate claims could not be verified against the exact retrieved sentences in the original PDFs.',
          suggestion: 'In accordance with zero-fabrication standards, ungrounded claims have been omitted.',
        };
      default:
        return {
          title: 'Insufficient Evidentiary Grounding',
          description:
            'The indexed papers do not contain sufficient evidence to answer this inquiry without speculation. ORION strictly abstains rather than producing hallucinated citations.',
          suggestion: 'Consider reviewing the source documents directly or refining the question with targeted terminology.',
        };
    }
  };

  const details = getReasonDetails(reasonCode);

  return (
    <div
      data-testid="abstention-banner"
      className="p-4 rounded-lg border border-reading-highlight/50 bg-reading-highlight-bg text-ink space-y-3 font-sans shadow-paper animate-in fade-in-0 duration-150"
    >
      <div className="flex items-start gap-2.5">
        <Compass className="w-5 h-5 text-reading-highlight shrink-0 mt-0.5" />
        <div className="min-w-0 flex-1">
          <div className="font-serif font-semibold text-sm text-ink">
            {details.title}
          </div>
          <p className="text-xs text-ink-secondary mt-1 leading-relaxed font-sans">
            {details.description}
          </p>
        </div>
      </div>

      <div className="pl-7 pt-2 border-t border-reading-highlight/20 flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-1.5 text-ink-secondary">
          <BookOpen className="w-3.5 h-3.5 text-reading-primary shrink-0" />
          <span className="font-medium text-ink">Scholarly Suggestion:</span>
          <span>{details.suggestion}</span>
        </div>

        {onOpenSources && (
          <button
            type="button"
            onClick={onOpenSources}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-paper-card hover:bg-paper-surface border border-border-hairline text-[11px] font-mono text-reading-primary transition-colors shrink-0"
          >
            <Layers className="w-3 h-3" />
            <span>Adjust Scope Sources</span>
          </button>
        )}
      </div>

      {traceId && (
        <div className="pl-7 text-[10px] font-mono text-ink-muted">
          Verification Trace ID: {traceId}
        </div>
      )}
    </div>
  );
};
