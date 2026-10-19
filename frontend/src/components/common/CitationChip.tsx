import React from 'react';
import { BookOpen } from 'lucide-react';
import { CitationItem } from '../../types';

interface CitationChipProps {
  citation: CitationItem;
  onClick?: (citation: CitationItem) => void;
  isActive?: boolean;
}

export const CitationChip: React.FC<CitationChipProps> = ({
  citation,
  onClick,
  isActive = false,
}) => {
  const pagesText =
    citation.page_numbers && citation.page_numbers.length > 0
      ? `p. ${citation.page_numbers.join(', ')}`
      : 'p. 1';

  return (
    <button
      type="button"
      onClick={() => onClick?.(citation)}
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono transition-all border ${
        isActive
          ? 'bg-navy-700 text-white border-navy-800 shadow-sm'
          : 'bg-parchment-100 hover:bg-parchment-200 text-navy-900 border-parchment-300 hover:border-navy-400'
      }`}
      title={`${citation.filename} (${pagesText})`}
    >
      <BookOpen className="w-3 h-3 opacity-70" />
      <span className="font-semibold">[{citation.citation_id}]</span>
      <span className="truncate max-w-[120px] opacity-80">{citation.filename}</span>
      <span className="opacity-60">{pagesText}</span>
    </button>
  );
};
