import React from 'react';
import { HelpCircle, ArrowRight, X } from 'lucide-react';
import { DocumentItem } from '../../types';
import { getPaperInk, getPaperInitial } from '../../utils/paperInks';

export interface ScopeGuardPromptProps {
  question: string;
  selectedDocuments: DocumentItem[];
  onSelectSingleDoc: (docId: string) => void;
  onContinueAll: () => void;
}

export function shouldTriggerScopeGuard(question: string, selectedCount: number): boolean {
  if (selectedCount <= 1) return false;
  const pattern = /\b(this|the)\s+(paper|study|article|research|document|report)\b/i;
  return pattern.test(question);
}

export const ScopeGuardPrompt: React.FC<ScopeGuardPromptProps> = ({
  question,
  selectedDocuments,
  onSelectSingleDoc,
  onContinueAll,
}) => {
  const isTriggered = shouldTriggerScopeGuard(question, selectedDocuments.length);
  if (!isTriggered) return null;

  return (
    <div
      data-testid="scope-guard-prompt"
      className="p-3.5 mb-2.5 rounded-lg border border-reading-highlight/40 bg-reading-highlight-bg text-ink text-xs shadow-paper animate-in fade-in-0 duration-150"
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-1.5 font-sans font-semibold text-ink">
          <HelpCircle className="w-4 h-4 text-reading-primary shrink-0" />
          <span>Which paper?</span>
        </div>

        <button
          type="button"
          onClick={onContinueAll}
          className="text-[11px] font-mono text-ink-muted hover:text-ink flex items-center gap-1 transition-colors"
        >
          <span>Continue with all</span>
          <ArrowRight className="w-3 h-3" />
        </button>
      </div>

      <p className="text-[11px] text-ink-secondary mb-2.5 leading-relaxed font-sans">
        Your question refers to a specific paper, but <span className="font-semibold text-ink">{selectedDocuments.length} sources</span> are currently selected. Focus the query on one paper:
      </p>

      {/* One-click paper chips to narrow scope */}
      <div className="flex flex-wrap gap-1.5">
        {selectedDocuments.map((doc, idx) => {
          const ink = getPaperInk(doc.filename || doc.id, idx);
          const initial = getPaperInitial(doc.filename);
          return (
            <button
              key={doc.id}
              type="button"
              onClick={() => onSelectSingleDoc(doc.id)}
              className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-paper-card hover:bg-paper-surface border text-[11px] font-mono text-ink shadow-xs transition-all hover:scale-[1.02] focus:outline-none focus:ring-1 focus:ring-reading-primary"
              style={{ borderColor: ink.borderLight }}
            >
              <span
                className="w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold text-white shrink-0"
                style={{ backgroundColor: ink.hex }}
              >
                {initial}
              </span>
              <span className="truncate max-w-[140px] sm:max-w-[200px]">{doc.filename}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
