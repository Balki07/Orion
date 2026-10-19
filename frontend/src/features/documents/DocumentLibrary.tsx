import React, { useState, useEffect } from 'react';
import {
  Search,
  Filter,
  Upload,
  RefreshCw,
  Trash2,
  FileText,
  Eye,
  AlertCircle,
  Clock,
  Layers,
} from 'lucide-react';
import { DocumentItem, CollectionItem } from '../../types';
import { api } from '../../services/api';
import { StatusBadge } from '../../components/common/StatusBadge';
import { UploadModal } from './UploadModal';
import { DocumentDetailModal } from './DocumentDetailModal';

export const DocumentLibrary: React.FC = () => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [collections, setCollections] = useState<CollectionItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [selectedCollectionId, setSelectedCollectionId] = useState<string>('');
  const [isUploadOpen, setIsUploadOpen] = useState<boolean>(false);
  const [detailDoc, setDetailDoc] = useState<DocumentItem | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchDocuments = async () => {
    try {
      const data = await api.listDocuments({
        search: searchTerm || undefined,
        status: statusFilter || undefined,
        collection_id: selectedCollectionId || undefined,
      });
      setDocuments(data.items);
      setIsLoading(false);
    } catch (err) {
      console.error('Failed to load documents:', err);
      setIsLoading(false);
    }
  };

  const fetchCollections = async () => {
    try {
      const data = await api.listCollections();
      setCollections(data.items);
    } catch (err) {
      console.error('Failed to load collections:', err);
    }
  };

  useEffect(() => {
    fetchDocuments();
    fetchCollections();
  }, [searchTerm, statusFilter, selectedCollectionId]);

  // Polling for documents in non-final states
  useEffect(() => {
    const hasInFlight = documents.some(
      (d) => d.status !== 'completed' && d.status !== 'failed'
    );
    if (!hasInFlight) return;

    const interval = setInterval(() => {
      fetchDocuments();
    }, 2500);

    return () => clearInterval(interval);
  }, [documents]);

  const handleDelete = async (docId: string, filename: string) => {
    if (!window.confirm(`Are you sure you want to permanently delete '${filename}' and purge all chunks from memory?`)) {
      return;
    }
    setDeletingId(docId);
    try {
      await api.deleteDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      setDeletingId(null);
    } catch (err: any) {
      alert(`Deletion failed: ${err.message}`);
      setDeletingId(null);
    }
  };

  const handleRetry = async (docId: string) => {
    try {
      await api.retryIngestion(docId);
      fetchDocuments();
    } catch (err: any) {
      alert(`Retry failed: ${err.message}`);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Title & Actions Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-serif font-bold text-ink-950">
            Document Library
          </h1>
          <p className="text-xs text-ink-500 mt-1">
            Research papers extracted page-by-page, chunked, and stored with 384-dimensional pgvector embeddings.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={fetchDocuments}
            className="p-2 rounded-lg border border-parchment-300 hover:bg-parchment-100 text-ink-700 transition-colors"
            title="Refresh document status"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={() => setIsUploadOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-navy-800 hover:bg-navy-900 text-white rounded-lg shadow-subtle text-sm font-medium transition-all"
          >
            <Upload className="w-4 h-4" />
            <span>Upload Research PDF</span>
          </button>
        </div>
      </div>

      {/* Filters & Search */}
      <div className="flex flex-wrap items-center gap-3 p-4 bg-white rounded-xl border border-parchment-300 shadow-xs">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 absolute left-3 top-3 text-ink-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search documents by filename..."
            className="w-full pl-9 pr-3 py-2 text-sm bg-parchment-50 border border-parchment-300 rounded-lg text-ink-900 focus:outline-hidden focus:ring-1 focus:ring-navy-600"
          />
        </div>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 text-sm bg-parchment-50 border border-parchment-300 rounded-lg text-ink-800"
        >
          <option value="">All Statuses</option>
          <option value="completed">Indexed & Ready</option>
          <option value="extracting">Extracting / Ingesting</option>
          <option value="failed">Failed</option>
        </select>

        {collections.length > 0 && (
          <select
            value={selectedCollectionId}
            onChange={(e) => setSelectedCollectionId(e.target.value)}
            className="px-3 py-2 text-sm bg-parchment-50 border border-parchment-300 rounded-lg text-ink-800"
          >
            <option value="">All Collections</option>
            {collections.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Document Table */}
      <div className="bg-white rounded-xl border border-parchment-300 shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-ink-500 font-mono text-sm">
            Loading document library...
          </div>
        ) : documents.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <div className="w-12 h-12 rounded-full bg-parchment-100 mx-auto flex items-center justify-center text-ink-400">
              <FileText className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-semibold text-ink-800">
              No research papers found
            </h3>
            <p className="text-xs text-ink-500 max-w-sm mx-auto">
              Upload your first scientific PDF to extract text with page provenance and begin evidence-grounded research.
            </p>
            <button
              type="button"
              onClick={() => setIsUploadOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2 mt-2 bg-navy-800 hover:bg-navy-900 text-white rounded-lg text-xs font-medium"
            >
              <Upload className="w-3.5 h-3.5" />
              <span>Upload Document</span>
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-parchment-100 border-b border-parchment-300 text-ink-600 font-mono uppercase tracking-wider">
                  <th className="py-3 px-4 font-semibold">Document Title</th>
                  <th className="py-3 px-4 font-semibold">Status</th>
                  <th className="py-3 px-4 font-semibold">Pages</th>
                  <th className="py-3 px-4 font-semibold">Chunks</th>
                  <th className="py-3 px-4 font-semibold">Size</th>
                  <th className="py-3 px-4 font-semibold">Date Added</th>
                  <th className="py-3 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-parchment-200 text-ink-900">
                {documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-parchment-50/80 transition-colors">
                    <td className="py-3 px-4 font-medium flex items-center gap-2.5">
                      <FileText className="w-4 h-4 text-navy-700 shrink-0" />
                      <span className="truncate max-w-xs">{doc.filename}</span>
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={doc.status} />
                    </td>
                    <td className="py-3 px-4 font-mono">
                      {doc.page_count > 0 ? `${doc.page_count} pp` : '—'}
                    </td>
                    <td className="py-3 px-4 font-mono">
                      {doc.chunk_count > 0 ? doc.chunk_count : '—'}
                    </td>
                    <td className="py-3 px-4 font-mono text-ink-500">
                      {(doc.file_size / (1024 * 1024)).toFixed(2)} MB
                    </td>
                    <td className="py-3 px-4 font-mono text-ink-500">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4 text-right space-x-1">
                      <button
                        type="button"
                        onClick={() => setDetailDoc(doc)}
                        className="p-1.5 rounded text-ink-600 hover:text-navy-800 hover:bg-parchment-200 transition-colors"
                        title="Inspect Document Pages & Metadata"
                      >
                        <Eye className="w-4 h-4" />
                      </button>

                      {doc.status === 'failed' && (
                        <button
                          type="button"
                          onClick={() => handleRetry(doc.id)}
                          className="p-1.5 rounded text-amber-600 hover:text-amber-800 hover:bg-amber-50 transition-colors"
                          title="Retry Ingestion"
                        >
                          <RefreshCw className="w-4 h-4" />
                        </button>
                      )}

                      <button
                        type="button"
                        disabled={deletingId === doc.id}
                        onClick={() => handleDelete(doc.id, doc.filename)}
                        className="p-1.5 rounded text-ink-400 hover:text-red-700 hover:bg-red-50 transition-colors"
                        title="Delete Document & Chunks"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Upload and Detail Modals */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={fetchDocuments}
        collections={collections}
      />

      <DocumentDetailModal
        document={detailDoc}
        onClose={() => setDetailDoc(null)}
      />
    </div>
  );
};
