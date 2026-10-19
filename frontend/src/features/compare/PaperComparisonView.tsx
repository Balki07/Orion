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
} from 'lucide-react';
import { DocumentItem, PaperComparisonResult } from '../../types';
import { api } from '../../services/api';
import { CitationChip } from '../../components/common/CitationChip';

export const PaperComparisonView: React.FC = () => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [comparisonResult, setComparisonResult] = useState<PaperComparisonResult | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const data = await api.listDocuments({ status: 'completed' });
      setDocuments(data.items);
      // Select first two documents by default if available
      if (data.items.length >= 2 && selectedDocIds.length === 0) {
        setSelectedDocIds([data.items[0].id, data.items[1].id]);
      }
    } catch (err) {
      console.error('Failed to load documents for comparison:', err);
    }
  };

  const toggleDocument = (id: string) => {
    if (selectedDocIds.includes(id)) {
      setSelectedDocIds((prev) => prev.filter((dId) => dId !== id));
    } else {
      if (selectedDocIds.length >= 5) {
        alert('You can compare a maximum of 5 documents simultaneously.');
        return;
      }
      setSelectedDocIds((prev) => [...prev, id]);
    }
  };

  const handleCompare = async () => {
    if (selectedDocIds.length < 2) {
      setErrorMessage('Please select at least 2 completed research papers to compare.');
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const res = await api.comparePapers(selectedDocIds);
      setComparisonResult(res);
      setIsLoading(false);
    } catch (err: any) {
      setIsLoading(false);
      setErrorMessage(err.message || 'Comparison failed.');
    }
  };

  const dimensions = [
    { key: 'problem', label: '1. Research Problem & Motivation' },
    { key: 'methodology', label: '2. Proposed Methodology & Architecture' },
    { key: 'datasets', label: '3. Training & Evaluation Datasets' },
    { key: 'results', label: '4. Reported Empirical Results & Benchmarks' },
    { key: 'limitations', label: '5. Documented Limitations & Compute Costs' },
    { key: 'future_work', label: '6. Identified Future Work & Open Questions' },
  ];

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-serif font-bold text-ink-950">
            Multi-Paper Comparative Synthesis
          </h1>
          <p className="text-xs text-ink-500 mt-1">
            Side-by-side evidence analysis across methodology, benchmarks, and limitations with verified citations.
          </p>
        </div>
        <button
          type="button"
          onClick={handleCompare}
          disabled={selectedDocIds.length < 2 || isLoading}
          className="flex items-center gap-2 px-5 py-2.5 bg-navy-800 hover:bg-navy-900 disabled:opacity-50 text-white rounded-lg shadow-subtle text-sm font-medium transition-all"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Analyzing Papers...</span>
            </>
          ) : (
            <>
              <GitCompare className="w-4 h-4" />
              <span>Compare Selected ({selectedDocIds.length})</span>
            </>
          )}
        </button>
      </div>

      {/* Document Selector Pills */}
      <div className="p-4 bg-white rounded-xl border border-parchment-300 shadow-xs space-y-2">
        <span className="text-xs font-mono uppercase tracking-wider text-ink-500 block">
          Select 2 to 5 Papers to Compare:
        </span>
        <div className="flex flex-wrap gap-2">
          {documents.map((doc) => {
            const isSelected = selectedDocIds.includes(doc.id);
            return (
              <button
                key={doc.id}
                type="button"
                onClick={() => toggleDocument(doc.id)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                  isSelected
                    ? 'bg-navy-800 text-white border-navy-900 shadow-xs'
                    : 'bg-parchment-50 hover:bg-parchment-100 text-ink-800 border-parchment-300'
                }`}
              >
                <FileText className="w-3.5 h-3.5 opacity-70" />
                <span className="truncate max-w-[200px]">{doc.filename}</span>
              </button>
            );
          })}
        </div>
      </div>

      {errorMessage && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg">
          {errorMessage}
        </div>
      )}

      {/* Comparison Results Table */}
      {comparisonResult ? (
        <div className="space-y-6">
          {/* Overarching Synthesis Card */}
          <div className="p-5 bg-white rounded-xl border border-parchment-300 shadow-xs space-y-3">
            <div className="flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-wider text-navy-800">
              <Sparkles className="w-4 h-4 text-navy-700" />
              <span>Comparative Evidence Synthesis</span>
            </div>
            <p className="text-xs font-serif leading-relaxed text-ink-900">
              {comparisonResult.synthesis}
            </p>
          </div>

          {/* Side-by-Side Matrix */}
          <div className="bg-white rounded-xl border border-parchment-300 shadow-xs overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-xs">
                <thead>
                  <tr className="bg-parchment-100 border-b border-parchment-300 font-serif">
                    <th className="py-3 px-4 font-bold text-ink-800 w-48 text-left uppercase text-[10px] font-mono tracking-wider">
                      Comparison Dimension
                    </th>
                    {comparisonResult.documents.map((d) => (
                      <th
                        key={d.document_id}
                        className="py-3 px-4 font-bold text-ink-950 text-left min-w-[260px] border-l border-parchment-200"
                      >
                        <div className="truncate max-w-xs">{d.filename}</div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-parchment-200 text-ink-900">
                  {dimensions.map((dim) => (
                    <tr key={dim.key} className="hover:bg-parchment-50/50 transition-colors">
                      <td className="py-4 px-4 font-semibold text-ink-700 bg-parchment-50/50 align-top">
                        {dim.label}
                      </td>
                      {comparisonResult.documents.map((d) => {
                        const field = d.fields[dim.key];
                        return (
                          <td
                            key={d.document_id}
                            className="py-4 px-4 align-top border-l border-parchment-200 space-y-2"
                          >
                            <p
                              className={`leading-relaxed font-serif ${
                                field?.is_missing
                                  ? 'italic text-ink-400'
                                  : 'text-ink-900'
                              }`}
                            >
                              {field?.extracted_text || 'Not found in the provided sources.'}
                            </p>

                            {/* Field Citations */}
                            {field?.citations && field.citations.length > 0 && (
                              <div className="flex flex-wrap gap-1 pt-1">
                                {field.citations.map((cite) => (
                                  <CitationChip key={cite.citation_id} citation={cite} />
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
        <div className="p-16 bg-white rounded-xl border border-parchment-300 text-center space-y-3">
          <GitCompare className="w-10 h-10 mx-auto text-ink-400" />
          <h3 className="text-sm font-serif font-bold text-ink-800">
            Select 2 or more research papers and click "Compare Selected"
          </h3>
          <p className="text-xs text-ink-500 max-w-md mx-auto">
            ORION retrieves evidence independently per document for standard comparison dimensions and detects conflicting findings.
          </p>
        </div>
      )}
    </div>
  );
};
