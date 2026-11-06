import React, { useState, useRef, useEffect } from 'react';
import {
  Upload,
  X,
  FileText,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Trash2,
  Plus,
  RefreshCw,
  AlertTriangle,
} from 'lucide-react';
import { api } from '../../services/api';
import { CollectionItem } from '../../types';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess: () => void;
  collections?: CollectionItem[];
}

export interface UploadFileItem {
  id: string;
  file: File;
  name: string;
  size: number;
  isValid: boolean;
  validationError?: string;
  status: 'selected' | 'uploading' | 'processing' | 'completed' | 'failed';
  docId?: string;
  progressPercentage: number;
  phase?: string;
  error?: string;
}

const MAX_PER_FILE_BYTES = 32 * 1024 * 1024; // 32MB
const MAX_BATCH_FILES = 10;
const MAX_BATCH_BYTES = 128 * 1024 * 1024; // 128MB

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
};

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  onUploadSuccess,
  collections = [],
}) => {
  const [dragActive, setDragActive] = useState(false);
  const [uploadItems, setUploadItems] = useState<UploadFileItem[]>([]);
  const [selectedCollectionId, setSelectedCollectionId] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [bannerWarning, setBannerWarning] = useState<string | null>(null);
  const [generalError, setGeneralError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Close on Escape key (if not currently uploading/submitting)
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isSubmitting) {
        handleModalClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isSubmitting]);

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setBannerWarning(null);
      setGeneralError(null);
    }
  }, [isOpen]);

  // Polling for processing documents using actual backend status
  useEffect(() => {
    const processingItems = uploadItems.filter(
      (item) => item.status === 'processing' && item.docId
    );
    if (processingItems.length === 0) return;

    let isMounted = true;
    const pollInterval = setInterval(async () => {
      try {
        const updates = await Promise.all(
          processingItems.map(async (item) => {
            try {
              const statusData = await api.getDocumentStatus(item.docId!);
              return { id: item.id, statusData };
            } catch (err: any) {
              return { id: item.id, error: err.message || 'Status check failed' };
            }
          })
        );

        if (!isMounted) return;

        setUploadItems((prev) =>
          prev.map((item) => {
            const update = updates.find((u) => u.id === item.id);
            if (!update) return item;

            if (update.error || !update.statusData) {
              return {
                ...item,
                status: 'failed',
                error: update.error || 'Status check failed',
              };
            }

            const statusData = update.statusData;
            if (statusData.status === 'completed' || statusData.status === 'ready') {
              return {
                ...item,
                status: 'completed',
                progressPercentage: 100,
                phase: 'completed',
              };
            }
            if (statusData.status === 'failed') {
              return {
                ...item,
                status: 'failed',
                error: statusData.error || 'Ingestion failed during processing.',
              };
            }
            return {
              ...item,
              progressPercentage: statusData.progress_percentage || item.progressPercentage,
              phase: statusData.status,
            };
          })
        );
      } catch (err) {
        console.error('Polling error:', err);
      }
    }, 2000);

    return () => {
      isMounted = false;
      clearInterval(pollInterval);
    };
  }, [uploadItems]);

  if (!isOpen) return null;

  const addFiles = (newFiles: FileList | File[]) => {
    setBannerWarning(null);
    setGeneralError(null);
    const incoming = Array.from(newFiles);

    setUploadItems((prev) => {
      const existingKeys = new Set(prev.map((item) => `${item.name}-${item.size}`));
      const duplicates: string[] = [];
      const updated = [...prev];

      for (const f of incoming) {
        const key = `${f.name}-${f.size}`;
        if (existingKeys.has(key)) {
          duplicates.push(f.name);
          continue;
        }

        if (updated.length >= MAX_BATCH_FILES) {
          setBannerWarning(`Maximum limit of ${MAX_BATCH_FILES} research papers per batch reached.`);
          break;
        }

        existingKeys.add(key);
        let isValid = true;
        let validationError: string | undefined;

        if (!f.name.toLowerCase().endsWith('.pdf')) {
          isValid = false;
          validationError = 'Not a PDF (.pdf required)';
        } else if (f.size === 0) {
          isValid = false;
          validationError = 'File is empty (0 bytes)';
        } else if (f.size > MAX_PER_FILE_BYTES) {
          isValid = false;
          validationError = `Exceeds ${formatBytes(MAX_PER_FILE_BYTES)} limit`;
        }

        updated.push({
          id: `${f.name}-${f.size}-${Math.random().toString(36).slice(2, 7)}`,
          file: f,
          name: f.name,
          size: f.size,
          isValid,
          validationError,
          status: 'selected',
          progressPercentage: 0,
        });
      }

      if (duplicates.length > 0) {
        setBannerWarning(`Ignored duplicate file(s): ${duplicates.join(', ')}`);
      }

      // Check total batch size
      const totalBytes = updated.reduce((sum, item) => sum + item.size, 0);
      if (totalBytes > MAX_BATCH_BYTES) {
        setBannerWarning(`Total batch size (${formatBytes(totalBytes)}) exceeds the ${formatBytes(MAX_BATCH_BYTES)} limit.`);
      }

      return updated;
    });
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addFiles(e.dataTransfer.files);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFiles(e.target.files);
      // Reset input value so re-selecting same file works
      e.target.value = '';
    }
  };

  const removeFile = (id: string) => {
    setUploadItems((prev) => prev.filter((item) => item.id !== id));
  };

  const clearAll = () => {
    setUploadItems([]);
    setBannerWarning(null);
    setGeneralError(null);
  };

  const validSelectedItems = uploadItems.filter(
    (item) => item.isValid && (item.status === 'selected' || item.status === 'failed')
  );
  const totalBatchBytes = uploadItems.reduce((acc, item) => acc + item.size, 0);

  const completedCount = uploadItems.filter((i) => i.status === 'completed').length;
  const processingCount = uploadItems.filter(
    (i) => i.status === 'uploading' || i.status === 'processing'
  ).length;
  const failedCount = uploadItems.filter((i) => i.status === 'failed').length;
  const isAnyInFlight = processingCount > 0 || isSubmitting;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (validSelectedItems.length === 0 || isAnyInFlight) return;

    if (totalBatchBytes > MAX_BATCH_BYTES) {
      setGeneralError(`Total batch size exceeds the limit of ${formatBytes(MAX_BATCH_BYTES)}.`);
      return;
    }

    setIsSubmitting(true);
    setGeneralError(null);

    const itemsToUpload = validSelectedItems;
    const targetFiles = itemsToUpload.map((i) => i.file);

    // Set initial uploading state
    setUploadItems((prev) =>
      prev.map((item) =>
        itemsToUpload.some((target) => target.id === item.id)
          ? { ...item, status: 'uploading', progressPercentage: 15, error: undefined }
          : item
      )
    );

    try {
      const response = await api.uploadDocumentsBatch(
        targetFiles,
        selectedCollectionId || undefined
      );

      // Map batch results to upload items
      setUploadItems((prev) =>
        prev.map((item) => {
          const res = response.items.find((r) => r.filename === item.name);
          if (!res) return item;

          if (res.status === 'rejected') {
            return {
              ...item,
              status: 'failed',
              error: res.error || 'File was rejected by backend validation.',
              progressPercentage: 0,
            };
          }

          if (res.status === 'completed') {
            return {
              ...item,
              status: 'completed',
              docId: res.document?.id,
              progressPercentage: 100,
              phase: 'completed',
            };
          }

          return {
            ...item,
            status: 'processing',
            docId: res.document?.id,
            progressPercentage: 25,
            phase: 'validating',
          };
        })
      );

      setIsSubmitting(false);

      // Trigger library refresh for newly queued documents
      if (response.successful_count > 0) {
        onUploadSuccess();
      }
    } catch (err: any) {
      setIsSubmitting(false);
      setGeneralError(err.message || 'Batch upload failed. Please check network and try again.');
      setUploadItems((prev) =>
        prev.map((item) =>
          itemsToUpload.some((target) => target.id === item.id)
            ? { ...item, status: 'failed', error: err.message || 'Upload failed' }
            : item
        )
      );
    }
  };

  const handleRetryItem = async (item: UploadFileItem) => {
    if (item.docId) {
      // Safe retry on backend without recreating document record
      setUploadItems((prev) =>
        prev.map((i) =>
          i.id === item.id
            ? { ...i, status: 'processing', progressPercentage: 20, error: undefined, phase: 'uploaded' }
            : i
        )
      );
      try {
        await api.retryIngestion(item.docId);
        onUploadSuccess();
      } catch (err: any) {
        setUploadItems((prev) =>
          prev.map((i) =>
            i.id === item.id ? { ...i, status: 'failed', error: err.message || 'Retry failed' } : i
          )
        );
      }
    } else {
      // Re-upload single file via single upload endpoint
      setUploadItems((prev) =>
        prev.map((i) =>
          i.id === item.id
            ? { ...i, status: 'uploading', progressPercentage: 15, error: undefined }
            : i
        )
      );
      try {
        const doc = await api.uploadDocument(item.file, selectedCollectionId || undefined);
        setUploadItems((prev) =>
          prev.map((i) =>
            i.id === item.id
              ? {
                  ...i,
                  status: doc.status === 'completed' ? 'completed' : 'processing',
                  docId: doc.id,
                  progressPercentage: doc.status === 'completed' ? 100 : 25,
                  phase: doc.status,
                }
              : i
          )
        );
        onUploadSuccess();
      } catch (err: any) {
        setUploadItems((prev) =>
          prev.map((i) =>
            i.id === item.id ? { ...i, status: 'failed', error: err.message || 'Upload failed' } : i
          )
        );
      }
    }
  };

  const handleModalClose = () => {
    if (completedCount > 0) {
      onUploadSuccess();
    }
    onClose();
  };

  // Determine footer button label
  const submitButtonLabel = () => {
    if (isSubmitting) return 'Uploading Batch...';
    if (processingCount > 0) return 'Indexing Papers...';
    if (validSelectedItems.length === 0 && completedCount > 0) return 'Done';
    const count = validSelectedItems.length;
    return count <= 1 ? 'Upload & Index 1 Paper' : `Upload & Index ${count} Papers`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/45 backdrop-blur-xs p-3 sm:p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Upload Research Papers"
        className="bg-white rounded-xl shadow-elevated border border-parchment-300 max-w-2xl w-full max-h-[92vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 sm:px-6 py-3.5 sm:py-4 border-b border-parchment-200 bg-parchment-50 shrink-0">
          <div>
            <h2 className="text-sm sm:text-base font-serif font-bold text-ink-950 flex items-center gap-2">
              <span>Upload Research Papers</span>
              {uploadItems.length > 0 && (
                <span className="text-[11px] font-mono font-medium px-2 py-0.5 rounded-full bg-navy-100 text-navy-800">
                  {uploadItems.length} {uploadItems.length === 1 ? 'paper' : 'papers'}
                </span>
              )}
            </h2>
            <p className="text-[11px] sm:text-xs text-ink-500 mt-0.5">
              Select or drop multiple technical PDFs to ingest and vectorize concurrently into ORION.
            </p>
          </div>
          <button
            type="button"
            onClick={handleModalClose}
            disabled={isSubmitting}
            aria-label="Close upload modal"
            className="p-1.5 rounded-md text-ink-400 hover:text-ink-700 hover:bg-parchment-200 transition-colors shrink-0 disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 min-h-0">
          {/* Drag & Drop Area */}
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-6 sm:p-8 text-center cursor-pointer transition-all ${
              dragActive
                ? 'border-navy-600 bg-navy-50/60 scale-[0.99]'
                : uploadItems.length > 0
                ? 'border-parchment-300 hover:border-navy-500 bg-parchment-50/60'
                : 'border-parchment-300 hover:border-navy-400 bg-parchment-50/40'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,application/pdf"
              onChange={handleFileChange}
              className="hidden"
            />

            <div className="flex flex-col items-center gap-2">
              <div className="w-11 h-11 rounded-full bg-navy-100 flex items-center justify-center text-navy-800 shrink-0">
                <Upload className="w-5 h-5" />
              </div>
              <p className="text-xs sm:text-sm font-medium text-ink-800">
                Drag and drop your PDF research papers here
              </p>
              <p className="text-[11px] text-ink-500">
                or <span className="text-navy-700 underline font-medium">browse local files</span> (max 10 PDFs, 32MB each, 128MB total batch)
              </p>
            </div>
          </div>

          {/* Banner Notifications */}
          {bannerWarning && (
            <div className="flex items-center gap-2 p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-xs">
              <AlertTriangle className="w-4 h-4 shrink-0 text-amber-700" />
              <span>{bannerWarning}</span>
            </div>
          )}

          {generalError && (
            <div className="flex items-center gap-2 p-2.5 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{generalError}</span>
            </div>
          )}

          {/* Batch Ingestion Status Summary Bar */}
          {uploadItems.length > 0 && (completedCount > 0 || processingCount > 0 || failedCount > 0) && (
            <div className="p-3 bg-parchment-100 rounded-lg border border-parchment-200 space-y-1.5">
              <div className="flex items-center justify-between text-[11px] font-mono text-ink-700">
                <span className="font-semibold uppercase tracking-wider">Batch Progress</span>
                <span>
                  {completedCount} of {uploadItems.length} Indexed
                </span>
              </div>
              <div className="w-full bg-parchment-300 h-1.5 rounded-full overflow-hidden">
                <div
                  className="bg-forest-600 h-full transition-all duration-300"
                  style={{
                    width: `${(completedCount / uploadItems.length) * 100}%`,
                  }}
                />
              </div>
              <div className="flex items-center gap-3 text-[10px] font-mono text-ink-500 pt-0.5">
                <span className="text-forest-700 font-medium">✓ {completedCount} Indexed</span>
                {processingCount > 0 && (
                  <span className="text-navy-700 font-medium">⏳ {processingCount} In-Flight</span>
                )}
                {failedCount > 0 && (
                  <span className="text-red-700 font-medium">✕ {failedCount} Failed</span>
                )}
              </div>
            </div>
          )}

          {/* Selected File List */}
          {uploadItems.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between px-1">
                <span className="text-xs font-semibold text-ink-800 uppercase tracking-wider font-mono">
                  Selected Papers ({uploadItems.length}) • {formatBytes(totalBatchBytes)}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isSubmitting || uploadItems.length >= MAX_BATCH_FILES}
                    className="flex items-center gap-1 text-[11px] font-medium text-navy-800 hover:text-navy-900 hover:underline disabled:opacity-40"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add More</span>
                  </button>
                  <span className="text-parchment-300">|</span>
                  <button
                    type="button"
                    onClick={clearAll}
                    disabled={isAnyInFlight}
                    className="text-[11px] font-medium text-ink-500 hover:text-red-600 hover:underline disabled:opacity-40"
                  >
                    Clear All
                  </button>
                </div>
              </div>

              <div className="max-h-52 sm:max-h-60 overflow-y-auto divide-y divide-parchment-200 border border-parchment-200 rounded-lg bg-white">
                {uploadItems.map((item) => (
                  <div
                    key={item.id}
                    className="p-2.5 sm:p-3 flex items-center justify-between gap-3 text-xs hover:bg-parchment-50/60 transition-colors"
                  >
                    <div className="flex items-center gap-2.5 min-w-0 flex-1">
                      <div
                        className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                          item.status === 'completed'
                            ? 'bg-forest-100 text-forest-700'
                            : item.status === 'failed' || !item.isValid
                            ? 'bg-red-100 text-red-700'
                            : 'bg-navy-50 text-navy-800'
                        }`}
                      >
                        <FileText className="w-4 h-4" />
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span
                            title={item.name}
                            className="font-medium text-ink-900 truncate max-w-xs sm:max-w-sm"
                          >
                            {item.name}
                          </span>
                          <span className="text-[10px] font-mono text-ink-400 shrink-0">
                            {formatBytes(item.size)}
                          </span>
                        </div>

                        {/* Status Label & Error Display */}
                        <div className="text-[11px] mt-0.5">
                          {!item.isValid ? (
                            <span className="text-red-600 font-medium">{item.validationError}</span>
                          ) : item.status === 'selected' ? (
                            <span className="text-ink-500">Ready to index</span>
                          ) : item.status === 'uploading' ? (
                            <span className="text-navy-700 font-medium flex items-center gap-1">
                              <Loader2 className="w-3 h-3 animate-spin shrink-0" />
                              <span>Uploading to storage...</span>
                            </span>
                          ) : item.status === 'processing' ? (
                            <span className="text-navy-700 font-medium flex items-center gap-1">
                              <Loader2 className="w-3 h-3 animate-spin shrink-0" />
                              <span className="capitalize">
                                {item.phase || 'Processing'} ({item.progressPercentage}%)
                              </span>
                            </span>
                          ) : item.status === 'completed' ? (
                            <span className="text-forest-700 font-medium flex items-center gap-1">
                              <CheckCircle2 className="w-3 h-3 shrink-0" />
                              <span>Indexed with citations</span>
                            </span>
                          ) : item.status === 'failed' ? (
                            <div className="flex items-center gap-2 text-red-600">
                              <span className="truncate max-w-xs" title={item.error}>{item.error || 'Ingestion failed'}</span>
                              <button
                                type="button"
                                onClick={() => handleRetryItem(item)}
                                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-red-100 hover:bg-red-200 text-red-800 text-[10px] font-medium transition-colors"
                              >
                                <RefreshCw className="w-2.5 h-2.5" />
                                <span>Retry</span>
                              </button>
                            </div>
                          ) : null}
                        </div>
                      </div>
                    </div>

                    {/* Remove Action Button (available before indexing or on failure) */}
                    {(item.status === 'selected' || item.status === 'failed') && (
                      <button
                        type="button"
                        onClick={() => removeFile(item.id)}
                        disabled={isSubmitting}
                        aria-label={`Remove ${item.name}`}
                        className="p-1 rounded text-ink-400 hover:text-red-600 hover:bg-parchment-200 transition-colors shrink-0"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Collection Assignment Dropdown */}
          {collections.length > 0 && (
            <div>
              <label className="block text-xs font-medium text-ink-700 mb-1">
                Assign to Research Collection (Optional)
              </label>
              <select
                value={selectedCollectionId}
                onChange={(e) => setSelectedCollectionId(e.target.value)}
                disabled={isAnyInFlight}
                className="w-full px-3 py-2 text-xs bg-white border border-parchment-300 rounded-lg text-ink-900 focus:outline-hidden focus:ring-1 focus:ring-navy-600 disabled:opacity-50"
              >
                <option value="">No collection (General Research Workspace)</option>
                {collections.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Footer Controls */}
          <div className="flex items-center justify-between pt-3 border-t border-parchment-200 shrink-0">
            <div className="text-xs font-mono text-ink-500">
              {uploadItems.length > 0 ? (
                <span>
                  <strong className="text-ink-800">{uploadItems.length}</strong>{' '}
                  {uploadItems.length === 1 ? 'file' : 'files'} selected ({formatBytes(totalBatchBytes)})
                </span>
              ) : (
                <span>No files selected</span>
              )}
            </div>

            <div className="flex items-center gap-2.5">
              <button
                type="button"
                onClick={handleModalClose}
                disabled={isSubmitting}
                className="px-3.5 py-1.5 text-xs font-medium text-ink-700 hover:bg-parchment-200 rounded-lg transition-colors disabled:opacity-50"
              >
                {completedCount > 0 && processingCount === 0 ? 'Close' : 'Cancel'}
              </button>

              {validSelectedItems.length === 0 && completedCount > 0 ? (
                <button
                  type="button"
                  onClick={handleModalClose}
                  className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium text-white bg-forest-700 hover:bg-forest-800 rounded-lg shadow-subtle transition-all"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Done</span>
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={validSelectedItems.length === 0 || isAnyInFlight || totalBatchBytes > MAX_BATCH_BYTES}
                  className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium text-white bg-navy-800 hover:bg-navy-900 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg shadow-subtle transition-all"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>{submitButtonLabel()}</span>
                    </>
                  ) : (
                    <>
                      <Upload className="w-3.5 h-3.5" />
                      <span>{submitButtonLabel()}</span>
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
