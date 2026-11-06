import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CitationItem } from '../../types';
import { CitationChip } from '../../components/common/CitationChip';

export interface AnswerRendererProps {
  content: string;
  citations?: CitationItem[];
  activeCitationId?: string | null;
  onCitationClick?: (citation: CitationItem) => void;
  className?: string;
}

export const AnswerRenderer: React.FC<AnswerRendererProps> = ({
  content,
  citations = [],
  activeCitationId,
  onCitationClick,
  className = '',
}) => {
  // Map raw citation tokens in text to markdown anchors matching our citations
  const transformedContent = useMemo(() => {
    if (!content || !citations || citations.length === 0) return content;

    // Build a quick lookup of valid citation IDs and their normalized forms
    const validIds = new Set<string>();
    for (const c of citations) {
      validIds.add(c.citation_id);
      validIds.add(c.citation_id.toLowerCase());
      const bare = c.citation_id.replace(/^cite:/i, '');
      validIds.add(bare);
      validIds.add(bare.toLowerCase());
    }

    // Replace [cite:X] or [X] when X corresponds to a valid citation
    // Match [cite:ID] or bracketed tokens like [1] or [SOMANTRI_P3]
    return content.replace(/\[(?:cite:)?([a-zA-Z0-9_\-.:]+)\]/g, (match, idToken) => {
      const trimmed = idToken.trim();
      if (validIds.has(trimmed) || validIds.has(trimmed.toLowerCase())) {
        return `[${match}](#cite:${trimmed})`;
      }
      return match;
    });
  }, [content, citations]);

  return (
    <div className={`reading-prose max-w-none text-ink ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children, ...props }) => {
            if (href?.startsWith('#cite:')) {
              const rawId = href.replace('#cite:', '').trim();
              const matchedCitation = citations.find((c) => {
                const cId = c.citation_id.trim();
                const cBare = cId.replace(/^cite:/i, '');
                return (
                  cId === rawId ||
                  cId.toLowerCase() === rawId.toLowerCase() ||
                  cBare === rawId ||
                  cBare.toLowerCase() === rawId.toLowerCase()
                );
              });

              if (matchedCitation) {
                return (
                  <CitationChip
                    citation={matchedCitation}
                    onClick={onCitationClick}
                    isActive={activeCitationId === matchedCitation.citation_id}
                    inline
                  />
                );
              }
            }

            // Normal link
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-reading-primary underline hover:text-ink font-medium"
                {...props}
              >
                {children}
              </a>
            );
          },
          h1: ({ children }) => (
            <h1 className="text-xl sm:text-2xl font-serif font-bold text-ink mb-3 mt-5 pb-1 border-b border-border-hairline">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-lg sm:text-xl font-serif font-bold text-ink mb-2.5 mt-4 pb-1 border-b border-border-subtle">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-base sm:text-lg font-serif font-semibold text-ink mb-2 mt-3.5 text-reading-primary">
              {children}
            </h3>
          ),
          p: ({ children }) => (
            <p className="text-xs sm:text-sm leading-relaxed mb-3 font-serif text-ink">
              {children}
            </p>
          ),
          ul: ({ children }) => (
            <ul className="list-disc pl-5 mb-3 space-y-1 text-xs sm:text-sm font-serif text-ink">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-5 mb-3 space-y-1 text-xs sm:text-sm font-serif text-ink">
              {children}
            </ol>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-3 border-reading-primary/40 pl-3.5 my-3 italic text-ink-secondary text-xs sm:text-sm font-serif bg-paper-raised/40 py-1 rounded-r">
              {children}
            </blockquote>
          ),
          code: ({ children, className }) => {
            const isBlock = className?.includes('language-');
            if (isBlock) {
              return (
                <pre className="p-3 my-2.5 rounded bg-paper-raised border border-border-hairline font-mono text-xs overflow-x-auto text-ink">
                  <code>{children}</code>
                </pre>
              );
            }
            return (
              <code className="px-1 py-0.5 rounded bg-paper-raised font-mono text-[11px] text-ink border border-border-hairline">
                {children}
              </code>
            );
          },
        }}
      >
        {transformedContent}
      </ReactMarkdown>
    </div>
  );
};
