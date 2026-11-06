import React, { useState, useEffect } from 'react';
import {
  GitCompare,
  FileText,
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Sparkles,
  Loader2,
  Layers,
  Compass,
  ArrowRight,
  ShieldCheck,
  Check,
  RotateCcw,
} from 'lucide-react';
import { DocumentItem, PaperComparisonResult, CitationItem } from '../../types';
import { api } from '../../services/api';
import { CitationChip } from '../../components/common/CitationChip';
import { getPaperInk, getPaperInitial } from '../../utils/paperInks';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { DocumentDetailModal } from '../documents/DocumentDetailModal';

export const PaperComparisonView: React.FC = () => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [comparisonResult, setComparisonResult] = useState<PaperComparisonResult | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isLoadingDocs, setIsLoadingDocs] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Modal inspection state for citation click
  const [inspectDoc, setInspectDoc] = useState<DocumentItem | null>(null);
  const [inspectPage, setInspectPage] = useState<number>(1);

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    setIsLoadingDocs(true);
    try {
      const data = await api.listDocuments({ status: 'completed' });
      setDocuments(data.items);
      // Select first two documents by default if available and not yet set
      if (data.items.length >= 2 && selectedDocIds.length === 0) {
        setSelectedDocIds([data.items[0].id, data.items[1].id]);
      }
    } catch (err: any) {
      console.error('Failed to load documents for comparison:', err);
      setErrorMessage(err?.message || 'Failed to load documents.');
    } finally {
      setIsLoadingDocs(false);
    }
  };

  const toggleDocument = (id: string) => {
    if (selectedDocIds.includes(id)) {
      setSelectedDocIds((prev) => prev.filter((dId) => dId !== id));
    } else {
      if (selectedDocIds.length >= 5) {
        setErrorMessage('You can compare a maximum of 5 documents simultaneously.');
        return;
      }
      setErrorMessage(null);
      setSelectedDocIds((prev) => [...prev, id]);
    }
  };

  const handleSelectAll = () => {
    setSelectedDocIds(documents.slice(0, 5).map((d) => d.id));
    setErrorMessage(null);
  };

  const handleClearSelection = () => {
    setSelectedDocIds([]);
    setErrorMessage(null);
  };

  const handleCompare = async () => {
    if (selectedDocIds.length < 2) {
      setErrorMessage('Please select at least 2 completed research publications to compare.');
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const res = await api.comparePapers(selectedDocIds);
      setComparisonResult(res);
    } catch (err: any) {
      setErrorMessage(err.message || 'Comparison synthesis failed.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCitationClick = (citation: CitationItem) => {
    const doc = documents.find((d) => d.id === citation.document_id);
    if (doc) {
      setInspectDoc(doc);
      setInspectPage(citation.page_numbers[0] || 1);
    }
  };

  const dimensions = [
    { key: 'problem', label: '1. Research Problem & Motivation', desc: 'Core objectives, scope, and motivation' },
    { key: 'methodology', label: '2. Proposed Methodology & Architecture', desc: 'Model architectures, algorithms, and design' },
    { key: 'datasets', label: '3. Training & Evaluation Datasets', desc: 'Corpora, domains, and data pipelines' },
    { key: 'results', label: '4. Reported Empirical Results & Benchmarks', desc: 'Evaluation metrics, scores, and baselines' },
    { key: 'limitations', label: '5. Documented Limitations & Compute Costs', desc: 'Known weaknesses, bounds, and compute constraints' },
    { key: 'future_work', label: '6. Identified Future Work & Open Questions', desc: 'Promising extensions and unaddressed areas' },
  ];

  return (
    <div
      className="p-4 sm:p-6 md:p-8 max-w-7xl mx-auto space-y-5 sm:space-y-6 font-sans text-ink select-none"
      data-testid="paper-comparison-view"
    >
      {/* Title & Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border-hairline">
        <div>
          <div className="flex items-center gap-2">
            <GitCompare className="w-5 h-5 text-reading-primary shrink-0" />
            <h1 className="text-xl sm:text-2xl font-serif font-bold text-ink">
              Multi-Paper Comparative Synthesis
            </h1>
          </div>
          <p className="text-xs sm:text-sm text-ink-secondary mt-1">
            Side-by-side evidence analysis across methodology, empirical benchmarks, and documented limitations with verified citations.
          </p>
        </div>

        <Button
          variant="primary"
          onClick={handleCompare}
          disabled={selectedDocIds.length < 2 || isLoading}
          className="self-start sm:self-auto gap-2 text-xs sm:text-sm px-4 py-2.5 shrink-0"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Synthesizing Evidence...</span>
            </>
          ) : (
            <>
              <GitCompare className="w-4 h-4" />
              <span>Compare Selected ({selectedDocIds.length})</span>
            </>
          )}
        </Button>
      </div>

      {/* Document Selector Pills Card */}
      <div className="p-4 bg-paper-surface rounded-xl border border-border-hairline shadow-subtle space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono uppercase tracking-wider text-ink-muted font-semibold">
              Select 2 to 5 Publications to Compare:
            </span>
            <span className="text-xs font-mono text-reading-primary">
              ({selectedDocIds.length} / 5 selected)
            </span>
          </div>

          <div className="flex items-center gap-2 text-xs">
            <button
              type="button"
              onClick={handleSelectAll}
              disabled={documents.length === 0}
              className="text-reading-primary hover:underline font-medium disabled:opacity-40"
            >
              Select First 5
            </button>
            <span className="text-border-hairline">&bull;</span>
            <button
              type="button"
              onClick={handleClearSelection}
              disabled={selectedDocIds.length === 0}
              className="text-ink-muted hover:text-ink font-medium disabled:opacity-40"
            >
              Clear
            </button>
          </div>
        </div>

        {/* Paper Pills */}
        {isLoadingDocs ? (
          <div className="py-6 flex items-center justify-center gap-2 text-xs text-ink-muted">
            <Loader2 className="w-4 h-4 animate-spin text-reading-primary" />
            <span>Loading publications from scope...</span>
          </div>
        ) : documents.length === 0 ? (
          <div className="p-6 text-center text-xs text-ink-muted bg-paper-bg rounded-lg border border-border-hairline space-y-1">
            <BookOpen className="w-5 h-5 mx-auto opacity-50 mb-2" />
            <div className="font-serif font-medium text-ink">No Completed Publications in Scope</div>
            <p className="max-w-md mx-auto text-ink-secondary">
              Please upload or index research papers into the active scope to enable comparative synthesis.
            </p>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2 pt-1">
            {documents.map((doc) => {
              const isSelected = selectedDocIds.includes(doc.id);
              const ink = getPaperInk(doc.filename);
              const initial = getPaperInitial(doc.filename);

              return (
                <button
                  key={doc.id}
                  type="button"
                  onClick={() => toggleDocument(doc.id)}
                  aria-pressed={isSelected}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all text-left ${
                    isSelected
                      ? 'bg-paper-card shadow-subtle border-reading-primary text-ink'
                      : 'bg-paper-bg hover:bg-paper-surface border-border-hairline text-ink-secondary opacity-75 hover:opacity-100'
                  }`}
                  style={isSelected ? { borderColor: ink.hex, borderLeftWidth: '3.5px' } : undefined}
                >
                  <span
                    className="w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold text-white shrink-0 shadow-xs"
                    style={{ backgroundColor: ink.hex }}
                  >
                    {initial}
                  </span>
                  <span className="truncate max-w-[180px] sm:max-w-[240px]">{doc.filename}</span>
                  <span className="text-[10px] font-mono text-ink-muted">({doc.page_count}p)</span>
                  {isSelected && <Check className="w-3.5 h-3.5 text-reading-primary shrink-0 ml-0.5" />}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Error Callout */}
      {errorMessage && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 text-red-700 dark:text-red-300 text-xs rounded-lg flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 text-red-600" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Comparison Results */}
      {comparisonResult ? (
        <div className="space-y-6 animate-in fade-in-0 duration-200">
          {/* 1. Overarching Synthesis Card */}
          <div className="p-5 sm:p-6 bg-paper-surface rounded-xl border border-border-hairline shadow-subtle space-y-3">
            <div className="flex items-center justify-between border-b border-border-subtle pb-2.5">
              <div className="flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-wider text-reading-primary">
                <Sparkles className="w-4 h-4 text-reading-primary" />
                <span>Evidence-Grounded Cross-Paper Synthesis</span>
              </div>
              <Badge variant="verified" size="sm">
                <ShieldCheck className="w-3 h-3 mr-1" />
                Multi-Source Grounded
              </Badge>
            </div>
            <p className="text-sm sm:text-base font-serif leading-relaxed text-ink selection:bg-highlight-bg">
              {comparisonResult.synthesis}
            </p>
          </div>

          {/* 2. Contradictions & Divergent Findings Section */}
          {comparisonResult.contradictions && comparisonResult.contradictions.length > 0 && (
            <div className="p-4 sm:p-5 bg-paper-surface rounded-xl border border-amber-500/30 shadow-subtle space-y-2.5">
              <div className="flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-wider text-amber-700 dark:text-amber-400">
                <AlertTriangle className="w-4 h-4 text-amber-600" />
                <span>Identified Contradictions &amp; Divergent Findings ({comparisonResult.contradictions.length})</span>
              </div>
              <ul className="space-y-2 pl-1">
                {comparisonResult.contradictions.map((contra, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-xs sm:text-sm font-serif text-ink leading-relaxed">
                    <span className="font-mono text-amber-600 text-xs font-bold mt-0.5">&bull;</span>
                    <span>{contra}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 3. Research Gaps Section */}
          {comparisonResult.research_gaps && comparisonResult.research_gaps.length > 0 && (
            <div className="p-4 sm:p-5 bg-paper-surface rounded-xl border border-border-hairline shadow-subtle space-y-2.5">
              <div className="flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-wider text-reading-primary">
                <Compass className="w-4 h-4 text-reading-primary" />
                <span>Identified Open Research Gaps ({comparisonResult.research_gaps.length})</span>
              </div>
              <ul className="space-y-2 pl-1">
                {comparisonResult.research_gaps.map((gap, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-xs sm:text-sm font-serif text-ink leading-relaxed">
                    <span className="font-mono text-reading-primary text-xs font-bold mt-0.5">&bull;</span>
                    <span>{gap}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 4. Side-by-Side Comparative Evidence Matrix */}
          <div className="bg-paper-surface rounded-xl border border-border-hairline shadow-subtle overflow-hidden">
            <div className="px-5 py-3 border-b border-border-hairline bg-paper-raised flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs font-mono font-semibold uppercase tracking-wider text-ink-muted">
                <Layers className="w-4 h-4 text-reading-primary" />
                <span>Side-by-Side Evidence Matrix</span>
              </div>
              <span className="text-xs font-mono text-ink-muted">
                {comparisonResult.documents.length} Publications &bull; {dimensions.length} Dimensions
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-xs">
                <thead>
                  <tr className="bg-paper-raised border-b border-border-hairline">
                    <th className="py-3 px-4 font-mono font-bold text-ink-muted w-52 text-left uppercase text-[10px] tracking-wider shrink-0">
                      Comparison Dimension
                    </th>
                    {comparisonResult.documents.map((d) => {
                      const ink = getPaperInk(d.filename);
                      const initial = getPaperInitial(d.filename);

                      return (
                        <th
                          key={d.document_id}
                          className="py-3 px-4 font-serif font-bold text-ink text-left min-w-[280px] border-l border-border-hairline"
                          style={{ borderTop: `3px solid ${ink.hex}` }}
                        >
                          <div className="flex items-center gap-2">
                            <span
                              className="w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold text-white shrink-0 shadow-xs"
                              style={{ backgroundColor: ink.hex }}
                            >
                              {initial}
                            </span>
                            <span className="truncate max-w-xs">{d.filename}</span>
                          </div>
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-subtle text-ink">
                  {dimensions.map((dim) => (
                    <tr key={dim.key} className="hover:bg-paper-bg/40 transition-colors">
                      <td className="py-4 px-4 bg-paper-raised/60 align-top shrink-0">
                        <div className="font-semibold text-ink text-xs font-sans">
                          {dim.label}
                        </div>
                        <div className="text-[10px] text-ink-muted mt-0.5 leading-tight">
                          {dim.desc}
                        </div>
                      </td>

                      {comparisonResult.documents.map((d) => {
                        const field = d.fields[dim.key];
                        const isMissing = field?.is_missing || !field?.extracted_text;

                        return (
                          <td
                            key={d.document_id}
                            className="py-4 px-4 align-top border-l border-border-subtle space-y-2.5"
                          >
                            <p
                              className={`leading-relaxed font-serif text-xs sm:text-sm ${
                                isMissing
                                  ? 'italic text-ink-muted'
                                  : 'text-ink'
                              }`}
                            >
                              {isMissing
                                ? 'No conclusive evidence found in this publication for this dimension.'
                                : field.extracted_text}
                            </p>

                            {/* Dimension Citations */}
                            {field?.citations && field.citations.length > 0 && (
                              <div className="flex flex-wrap gap-1.5 pt-1 border-t border-border-hairline/60">
                                {field.citations.map((cite) => (
                                  <CitationChip
                                    key={cite.citation_id}
                                    citation={cite}
                                    onClick={handleCitationClick}
                                  />
                                ))}
                              </div>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        /* Empty / Invitation State */
        <div className="p-12 sm:p-16 bg-paper-surface rounded-xl border border-border-hairline text-center space-y-4 shadow-subtle">
          <div className="w-12 h-12 rounded-full bg-paper-bg border border-border-hairline flex items-center justify-center text-ink-muted mx-auto">
            <GitCompare className="w-6 h-6 text-reading-primary opacity-80" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-serif font-bold text-ink">
              Ready for Multi-Paper Comparative Analysis
            </h3>
            <p className="text-xs sm:text-sm text-ink-secondary max-w-lg mx-auto leading-relaxed">
              Select 2 to 5 research publications above and click <strong>"Compare Selected"</strong>. ORION independently analyzes each paper across research problem, proposed methodology, datasets, empirical benchmarks, and documented limitations without hallucinating unverified claims.
            </p>
          </div>
          {selectedDocIds.length >= 2 && (
            <Button
              variant="primary"
              onClick={handleCompare}
              disabled={isLoading}
              className="gap-2 text-xs"
            >
              <GitCompare className="w-3.5 h-3.5" />
              <span>Launch Comparison ({selectedDocIds.length} Papers)</span>
            </Button>
          )}
        </div>
      )}

      {/* Document Detail Modal for clicking a citation inside the comparison table */}
      <DocumentDetailModal
        document={inspectDoc}
        initialPage={inspectPage}
        onClose={() => setInspectDoc(null)}
      />
    </div>
  );
};
