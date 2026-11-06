import React, { useState } from 'react';
import { Copy, Check, Bookmark, RefreshCw, Cpu, Clock, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';
import { CitationItem } from '../../types';

export interface AnswerActionsProps {
  content: string;
  citations?: CitationItem[];
  model?: string | null;
  answerPath?: 'gemini' | 'deterministic_fallback';
  fallbackReason?: string | null;
  latencyMs?: Record<string, number>;
  onRegenerate?: () => void;
  onSaveToNotes?: () => Promise<void>;
  isSavingNote?: boolean;
  isSavedNote?: boolean;
}

export const AnswerActions: React.FC<AnswerActionsProps> = ({
  content,
  citations = [],
  model,
  answerPath,
  fallbackReason,
  latencyMs,
  onRegenerate,
  onSaveToNotes,
  isSavingNote = false,
  isSavedNote = false,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopyWithCitations = async () => {
    try {
      let fullText = content;

      if (citations && citations.length > 0) {
        fullText += '\n\n### References\n';
        citations.forEach((cite, idx) => {
          const pages =
            cite.page_numbers && cite.page_numbers.length > 0
              ? `p. ${cite.page_numbers.join(', ')}`
              : 'p. 1';
          const citeNum = cite.citation_id.replace(/^cite:/i, '') || String(idx + 1);
          fullText += `[${citeNum}] ${cite.filename} (${pages}): "${cite.excerpt}"\n`;
        });
      }

      await navigator.clipboard.writeText(fullText);
      setCopied(true);
      toast.success('Answer and references copied to clipboard');
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error('Could not copy to clipboard');
    }
  };

  const isGemini = answerPath === 'gemini';
  const effectiveModel = isGemini ? (model || 'Gemini') : 'Deterministic mode';
  const fallbackLabel = fallbackReason === 'UNAVAILABLE'
    ? 'Provider high demand (503)'
    : fallbackReason || 'Basic mode';

  const totalLatency = latencyMs?.total ?? (latencyMs?.retrieval ? (latencyMs.retrieval + (latencyMs.generation || 0)) : undefined);

  return (
    <div
      data-testid="answer-actions-bar"
      className="pt-3 border-t border-border-hairline flex flex-wrap items-center justify-between gap-3 text-xs font-mono text-ink-muted"
    >
      {/* Action Buttons */}
      <div className="flex items-center gap-2 flex-wrap">
        <button
          type="button"
          onClick={handleCopyWithCitations}
          aria-label="Copy answer with references to clipboard"
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-paper-card hover:bg-paper-raised border border-border-hairline text-ink text-xs transition-colors focus:outline-none focus:ring-1 focus:ring-reading-primary"
        >
          {copied ? (
            <Check className="w-3.5 h-3.5 text-reading-verified" />
          ) : (
            <Copy className="w-3.5 h-3.5" />
          )}
          <span>{copied ? 'Copied' : 'Copy with Citations'}</span>
        </button>

        {onSaveToNotes && (
          <button
            type="button"
            onClick={onSaveToNotes}
            disabled={isSavingNote || isSavedNote}
            aria-label="Save answer to research notes"
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs transition-colors border focus:outline-none focus:ring-1 focus:ring-reading-primary ${
              isSavedNote
                ? 'bg-reading-verified-bg text-reading-verified border-reading-verified/30'
                : 'bg-paper-card hover:bg-paper-raised text-ink border-border-hairline'
            }`}
          >
            {isSavedNote ? (
              <CheckCircle2 className="w-3.5 h-3.5 text-reading-verified" />
            ) : (
              <Bookmark className="w-3.5 h-3.5" />
            )}
            <span>{isSavingNote ? 'Saving...' : isSavedNote ? 'Saved to Notes' : 'Save to Notes'}</span>
          </button>
        )}

        {onRegenerate && (
          <button
            type="button"
            onClick={onRegenerate}
            aria-label="Regenerate synthesis"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-paper-card hover:bg-paper-raised border border-border-hairline text-ink text-xs transition-colors focus:outline-none focus:ring-1 focus:ring-reading-primary"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Regenerate</span>
          </button>
        )}
      </div>

      {/* Model & Latency Attribution */}
      <div className="flex items-center gap-3 text-[11px] text-ink-secondary flex-wrap">
        <div
          data-testid="answer-model-attribution"
          className="flex items-center gap-1.5"
          title={
            isGemini
              ? `Generated via live Gemini API (${effectiveModel})`
              : `Generated via deterministic extractive synthesis (${fallbackLabel})`
          }
        >
          <span
            className={`w-2 h-2 rounded-full ${
              isGemini ? 'bg-reading-verified' : 'bg-reading-warning'
            }`}
          />
          <Cpu className="w-3 h-3 text-ink-muted" />
          <span className="font-semibold text-ink">{effectiveModel}</span>
        </div>

        {totalLatency !== undefined && (
          <div className="flex items-center gap-1 text-ink-muted" title="Total processing latency">
            <Clock className="w-3 h-3" />
            <span>{Math.round(totalLatency)} ms</span>
          </div>
        )}
      </div>
    </div>
  );
};
