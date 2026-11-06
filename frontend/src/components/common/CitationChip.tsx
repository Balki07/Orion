import React from 'react';
import { BookOpen } from 'lucide-react';
import { CitationItem } from '../../types';
import { getPaperInk, getPaperInitial } from '../../utils/paperInks';
import { Tooltip } from '../ui/Tooltip';

export interface CitationChipProps {
  citation: CitationItem;
  onClick?: (citation: CitationItem) => void;
  isActive?: boolean;
  inline?: boolean;
}

export const CitationChip: React.FC<CitationChipProps> = ({
  citation,
  onClick,
  isActive = false,
  inline = false,
}) => {
  const ink = getPaperInk(citation.filename || citation.document_id);
  const initial = getPaperInitial(citation.filename);

  const pagesText =
    citation.page_numbers && citation.page_numbers.length > 0
      ? `p. ${citation.page_numbers.join(', ')}`
      : 'p. 1';

  // Format short citation label (e.g. "cite:1" -> "1" or preserve custom ID)
  const displayLabel = String(citation.citation_id).replace(/^cite:/i, '');

  const tooltipContent = (
    <div className="max-w-xs space-y-1.5 p-1 text-left font-sans text-xs">
      <div className="flex items-center gap-1.5 font-semibold text-ink">
        <span
          className="w-3.5 h-3.5 rounded-full flex items-center justify-center text-[8px] font-bold text-white shrink-0"
          style={{ backgroundColor: ink.hex }}
        >
          {initial}
        </span>
        <span className="truncate">{citation.filename}</span>
        <span className="font-mono text-[10px] text-ink-muted">({pagesText})</span>
      </div>
      {citation.excerpt && (
        <p className="text-[11px] leading-relaxed text-ink-secondary italic line-clamp-3 border-l-2 pl-2" style={{ borderColor: ink.hex }}>
          "{citation.excerpt}"
        </p>
      )}
      <div className="text-[10px] font-mono text-reading-primary pt-0.5">
        Click to inspect evidence & page context →
      </div>
    </div>
  );

  if (inline) {
    return (
      <Tooltip content={tooltipContent}>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onClick?.(citation);
          }}
          aria-label={`Citation [${displayLabel}]: ${citation.filename}, ${pagesText}. Click to inspect evidence.`}
          className={`inline-flex items-center gap-1 px-1.5 py-0.5 mx-0.5 rounded text-[11px] font-mono align-baseline font-medium transition-all border shadow-2xs select-none focus:outline-none focus:ring-2 focus:ring-reading-primary ${
            isActive
              ? 'ring-2 ring-reading-primary shadow-subtle'
              : 'hover:scale-[1.03]'
          }`}
          style={{
            backgroundColor: isActive ? ink.hex : ink.bgLight,
            color: isActive ? '#FFFFFF' : ink.hex,
            borderColor: ink.borderLight,
          }}
        >
          <span
            className={`w-3.5 h-3.5 rounded-full flex items-center justify-center text-[8px] font-bold ${
              isActive ? 'bg-white/20 text-white' : 'text-white'
            }`}
            style={{ backgroundColor: isActive ? 'rgba(255,255,255,0.2)' : ink.hex }}
          >
            {initial}
          </span>
          <span>[{displayLabel}]</span>
        </button>
      </Tooltip>
    );
  }

  return (
    <Tooltip content={tooltipContent}>
      <button
        type="button"
        onClick={() => onClick?.(citation)}
        aria-label={`Citation [${displayLabel}]: ${citation.filename}, ${pagesText}. Click to inspect evidence.`}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono transition-all border shadow-xs select-none focus:outline-none focus:ring-2 focus:ring-reading-primary ${
          isActive
            ? 'ring-2 ring-reading-primary shadow-subtle font-semibold'
            : 'hover:scale-[1.02] bg-paper-card'
        }`}
        style={{
          borderColor: ink.borderLight,
          backgroundColor: isActive ? ink.bgLight : undefined,
        }}
      >
        <span
          className="w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold text-white shrink-0"
          style={{ backgroundColor: ink.hex }}
        >
          {initial}
        </span>
        <span className="font-semibold text-ink">[{citation.citation_id}]</span>
        <span className="truncate max-w-[140px] text-ink-secondary">{citation.filename}</span>
        <span className="text-ink-muted text-[10px] font-mono">{pagesText}</span>
      </button>
    </Tooltip>
  );
};
