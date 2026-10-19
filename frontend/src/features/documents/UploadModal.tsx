import React, { useState, useRef } from 'react';
import { Upload, X, FileText, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { api } from '../../services/api';
import { CollectionItem } from '../../types';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess: () => void;
  collections?: CollectionItem[];
}

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  onUploadSuccess,
  collections = [],
}) => {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedCollectionId, setSelectedCollectionId] = useState<string>('');
  const [isUploading, setIsUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

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
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (file: File) => {
    setErrorMessage(null);
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setErrorMessage('Only PDF documents are supported (.pdf).');
      return;
    }
    if (file.size > 32 * 1024 * 1024) {
      setErrorMessage('File size exceeds the 32MB limit.');
      return;
    }
    setSelectedFile(file);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    setIsUploading(true);
    setErrorMessage(null);

    try {
      await api.uploadDocument(selectedFile, selectedCollectionId || undefined);
      setIsUploading(false);
      setSelectedFile(null);
      onUploadSuccess();
      onClose();
    } catch (err: any) {
      setIsUploading(false);
      setErrorMessage(err.message || 'Failed to upload document.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/40 backdrop-blur-xs p-4">
      <div className="bg-white rounded-xl shadow-elevated border border-parchment-300 max-w-lg w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-center justify-between px-6 py-4 border-b border-parchment-200 bg-parchment-50">
          <div>
            <h2 className="text-base font-serif font-bold text-ink-950">
              Upload Research Document
            </h2>
            <p className="text-xs text-ink-500">
              PDFs will be extracted page-by-page and indexed with 384-dim BGE embeddings.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-md text-ink-400 hover:text-ink-700 hover:bg-parchment-200 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Drag and drop zone */}
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
              dragActive
                ? 'border-navy-600 bg-navy-50/50'
                : selectedFile
                ? 'border-forest-400 bg-forest-50/30'
                : 'border-parchment-300 hover:border-navy-400 bg-parchment-50/50'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,application/pdf"
              onChange={handleFileChange}
              className="hidden"
            />

            {selectedFile ? (
              <div className="flex flex-col items-center gap-2">
                <div className="w-12 h-12 rounded-full bg-forest-100 flex items-center justify-center text-forest-700">
                  <FileText className="w-6 h-6" />
                </div>
                <div className="text-sm font-medium text-ink-900 truncate max-w-xs">
                  {selectedFile.name}
                </div>
                <div className="text-xs font-mono text-ink-500">
                  {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                </div>
                <span className="text-xs text-navy-700 font-medium hover:underline mt-1">
                  Click to replace file
                </span>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <div className="w-12 h-12 rounded-full bg-parchment-200 flex items-center justify-center text-navy-800">
                  <Upload className="w-6 h-6" />
                </div>
                <p className="text-sm font-medium text-ink-800">
                  Drag and drop your PDF research paper here
                </p>
                <p className="text-xs text-ink-500">
                  or <span className="text-navy-700 underline font-medium">browse local files</span> (max 32MB)
                </p>
              </div>
            )}
          </div>

          {/* Collection assignment */}
          {collections.length > 0 && (
            <div>
              <label className="block text-xs font-medium text-ink-700 mb-1">
                Assign to Research Collection (Optional)
              </label>
              <select
                value={selectedCollectionId}
                onChange={(e) => setSelectedCollectionId(e.target.value)}
                className="w-full px-3 py-2 text-sm bg-white border border-parchment-300 rounded-lg text-ink-900 focus:outline-hidden focus:ring-1 focus:ring-navy-600"
              >
                <option value="">No collection (General Library)</option>
                {collections.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Error display */}
          {errorMessage && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-parchment-200">
            <button
              type="button"
              onClick={onClose}
              disabled={isUploading}
              className="px-4 py-2 text-sm font-medium text-ink-700 hover:bg-parchment-200 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!selectedFile || isUploading}
              className="flex items-center gap-2 px-5 py-2 text-sm font-medium text-white bg-navy-800 hover:bg-navy-900 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg shadow-subtle transition-all"
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Uploading & Ingesting...</span>
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4" />
                  <span>Start Ingestion</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
