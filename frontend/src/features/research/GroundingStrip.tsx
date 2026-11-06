import React, { useState } from 'react';
import { ShieldCheck, ChevronDown, ChevronUp, Link as LinkIcon } from 'lucide-react';
import { ClaimItem, CitationItem } from '../../types';
import { Badge } from '../../components/ui/Badge';

export interface GroundingStripProps {
  claims?: ClaimItem[];
  citations?: CitationItem[];
  onCitationClick?: (citation: CitationItem) => void;
}

export const GroundingStrip: React.FC<GroundingStripProps> = ({
  claims,
  citations = [],
  onCitationClick,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  // Requirement: Display grounding summary ONLY when API supplies trustworthy claim-support data.
  // Never invent supported-claim count or evidence score.
  if (!claims || claims.length === 0) {
    return null;
  }

  const supportedCount = claims.filter((c) => c.support_status === 'supported').length;
  const partiallySupportedCount = claims.filter((c) => c.support_status === 'partially_supported').length;
  const unsupportedCount = claims.filter((c) => c.support_status === 'unsupported').length;

  return (
    <div
      data-testid="grounding-strip"
      className="rounded-lg border border-border-hairline bg-paper-card p-3 font-sans text-xs shadow-2xs space-y-2 transition-all"
    >
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-reading-verified shrink-0" />
          <span className="font-semibold text-ink font-serif text-xs sm:text-sm">
            Claim Grounding Verification
          </span>
          <span className="text-[11px] font-mono text-ink-muted">
            ({claims.length} claims verified)
          </span>
        </div>

        <div className="flex items-center gap-1.5 flex-wrap">
          {supportedCount > 0 && (
            <Badge variant="verified" size="sm">
              {supportedCount} Supported
            </Badge>
          )}
          {partiallySupportedCount > 0 && (
            <Badge variant="warning" size="sm">
              {partiallySupportedCount} Partially Supported
            </Badge>
          )}
          {unsupportedCount > 0 && (
            <Badge variant="outline" size="sm" className="text-reading-warning border-reading-warning/30">
              {unsupportedCount} Unsupported
            </Badge>
          )}

          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            aria-expanded={isExpanded}
            aria-label="Toggle claims breakdown list"
            className="p-1 rounded text-ink-muted hover:text-ink hover:bg-paper-raised transition-colors ml-1"
          >
            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Expandable list of verified claims */}
      {isExpanded && (
        <div className="pt-2 mt-2 border-t border-border-subtle space-y-2 animate-in fade-in-0 duration-150">
          {claims.map((claim, idx) => {
            const isSupported = claim.support_status === 'supported';
            const isPartial = claim.support_status === 'partially_supported';

            return (
              <div
                key={idx}
                className="p-2.5 rounded bg-paper-surface border border-border-hairline space-y-1.5"
              >
                <div className="flex items-start justify-between gap-2">
                  <span
                    className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider ${
                      isSupported
                        ? 'bg-reading-verified-bg text-reading-verified font-medium'
                        : isPartial
                        ? 'bg-reading-highlight-bg text-reading-highlight font-medium'
                        : 'bg-reading-warning-bg text-reading-warning font-medium'
                    }`}
                  >
                    {claim.support_status.replace('_', ' ')}
                  </span>

                  {claim.citation_ids && claim.citation_ids.length > 0 && (
                    <div className="flex items-center gap-1 flex-wrap">
                      <span className="text-[10px] font-mono text-ink-muted flex items-center gap-0.5">
                        <LinkIcon className="w-3 h-3" />
                        Citations:
                      </span>
                      {claim.citation_ids.map((citeId) => {
                        const matchedCite = citations.find(
                          (c) =>
                            c.citation_id === citeId ||
                            c.citation_id.replace(/^cite:/i, '') === citeId
                        );

                        return (
                          <button
                            key={citeId}
                            type="button"
                            onClick={() => matchedCite && onCitationClick?.(matchedCite)}
                            disabled={!matchedCite}
                            className={`px-1.5 py-0.5 rounded text-[10px] font-mono border transition-colors ${
                              matchedCite
                                ? 'bg-paper-card hover:bg-paper-raised text-reading-primary border-border-hairline hover:border-reading-primary cursor-pointer'
                                : 'bg-paper-bg text-ink-muted border-border-subtle cursor-default'
                            }`}
                          >
                            [{citeId.replace(/^cite:/i, '')}]
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>

                <p className="text-xs text-ink leading-relaxed font-serif">
                  {claim.text}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
