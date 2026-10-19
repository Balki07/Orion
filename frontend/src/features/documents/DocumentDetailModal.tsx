import React, { useState, useEffect } from 'react';
import { X, FileText, AlertTriangle, Layers, BookOpen, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import { DocumentItem } from '../../types';
import { api } from '../../services/api';
import { StatusBadge } from '../../components/common/StatusBadge';

interface DocumentDetailModalProps {
  document: DocumentItem | null;
  onClose: () => void;
}

export const DocumentDetailModal: React.FC<DocumentDetailModalProps> = ({
  document,
  onClose,
}) => {
  const [activePage, setActivePage] = useState<number>(1);
  const [pageContent, setPageContent] = useState<string>('');
  const [isLoadingPage, setIsLoadingPage] = useState<boolean>(false);
  const [pageError, setPageError] = useState<string | null>(null);

  useEffect(() => {
    if (document && document.status === 'completed' && document.page_count > 0) {
      loadPage(1);
    }
  }, [document]);

  if (!document) return null;

  const loadPage = async (pageNumber: number) => {
    setActivePage(pageNumber);
    setIsLoadingPage(true);
    setPageError(null);
    try {
      const data = await api.getDocumentPage(document.id, pageNumber);
      setPageContent(data.text);
      setIsLoadingPage(false);
    } catch (err: any) {
      setPageError(err.message || 'Failed to fetch page text.');
      setIsLoadingPage(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/40 backdrop-blur-xs p-4">
      <div className="bg-white rounded-xl shadow-elevated border border-parchment-300 max-w-3xl w-full max-h-[85vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-parchment-200 bg-parchment-50">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-navy-100 flex items-center justify-center text-navy-800">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-ink-950 truncate max-w-md">
                {document.filename}
              </h2>
              <div className="flex items-center gap-2 mt-0.5">
                <StatusBadge status={document.status} />
                <span className="text-xs font-mono text-ink-500">
                  ID: {document.id}
                </span>
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-md text-ink-400 hover:text-ink-700 hover:bg-parchment-200 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          {/* Metadata Cards Grid */}
          <div className="grid grid-cols-4 gap-3 text-xs">
            <div className="p-3 bg-parchment-50 rounded-lg border border-parchment-200">
              <span className="text-ink-500 block mb-1">File Size</span>
              <span className="font-mono font-semibold text-ink-900">
                {(document.file_size / (1024 * 1024)).toFixed(2)} MB
              </span>
            </div>
            <div className="p-3 bg-parchment-50 rounded-lg border border-parchment-200">
              <span className="text-ink-500 block mb-1">Total Pages</span>
              <span className="font-mono font-semibold text-ink-900">
                {document.page_count} pages
              </span>
            </div>
            <div className="p-3 bg-parchment-50 rounded-lg border border-parchment-200">
              <span className="text-ink-500 block mb-1">Indexed Chunks</span>
              <span className="font-mono font-semibold text-ink-900">
                {document.chunk_count} chunks
              </span>
            </div>
            <div className="p-3 bg-parchment-50 rounded-lg border border-parchment-200">
              <span className="text-ink-500 block mb-1">Uploaded</span>
              <span className="font-mono text-ink-900">
                {new Date(document.created_at).toLocaleDateString()}
              </span>
            </div>
          </div>

          {/* Extraction Warnings */}
          {document.extraction_warnings && document.extraction_warnings.length > 0 && (
            <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg text-amber-900 text-xs space-y-1">
              <div className="flex items-center gap-2 font-semibold text-amber-800">
                <AlertTriangle className="w-4 h-4 text-amber-600" />
                <span>Extraction Warnings</span>
              </div>
              <ul className="list-disc pl-5 space-y-0.5">
                {document.extraction_warnings.map((w, idx) => (
                  <li key={idx}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Processing Error if failed */}
          {document.processing_error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-900 text-xs">
              <div className="font-semibold mb-1">Ingestion Failure Details:</div>
              <p className="font-mono text-red-800">{document.processing_error}</p>
            </div>
          )}

          {/* Page Inspector with Provenance */}
          {document.status === 'completed' && document.page_count > 0 && (
            <div className="border border-parchment-300 rounded-lg overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2.5 bg-parchment-100 border-b border-parchment-200">
                <div className="flex items-center gap-2 text-xs font-semibold text-navy-950">
                  <BookOpen className="w-4 h-4 text-navy-700" />
                  <span>Page Inspector & Provenance</span>
                </div>

                {/* Page pagination */}
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={activePage <= 1 || isLoadingPage}
                    onClick={() => loadPage(activePage - 1)}
                    className="p-1 rounded hover:bg-parchment-200 disabled:opacity-40 text-ink-700"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span className="text-xs font-mono text-ink-700">
                    Page {activePage} of {document.page_count}
                  </span>
                  <button
                    type="button"
                    disabled={activePage >= document.page_count || isLoadingPage}
                    onClick={() => loadPage(activePage + 1)}
                    className="p-1 rounded hover:bg-parchment-200 disabled:opacity-40 text-ink-700"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div className="p-4 bg-parchment-50 min-h-[220px] max-h-[300px] overflow-y-auto text-xs leading-relaxed font-serif text-ink-900">
                {isLoadingPage ? (
                  <div className="flex items-center justify-center h-32 gap-2 text-ink-500">
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Loading page text...</span>
                  </div>
                ) : pageError ? (
                  <div className="text-red-700">{pageError}</div>
                ) : (
                  <pre className="font-sans whitespace-pre-wrap select-text">{pageContent}</pre>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="px-6 py-3 border-t border-parchment-200 bg-parchment-50 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-ink-800 bg-parchment-200 hover:bg-parchment-300 rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
