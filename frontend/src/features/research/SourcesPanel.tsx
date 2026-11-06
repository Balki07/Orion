import React, { useState, useMemo } from 'react';
import { Layers, Search, X, Copy, CheckSquare, Square, AlertCircle, ChevronLeft, ChevronRight } from 'lucide-react';
import { DocumentItem } from '../../types';
import { getPaperInk, getPaperInitial } from '../../utils/paperInks';
import { Badge } from '../../components/ui/Badge';
import { Tooltip } from '../../components/ui/Tooltip';

export interface SourcesPanelProps {
  documents: DocumentItem[];
  selectedDocIds: string[];
  onToggleDoc: (docId: string) => void;
  onSelectAll: () => void;
  onDeselectDoc?: (docId: string) => void;
  onCloseDrawer?: () => void;
  isDrawer?: boolean;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

interface DuplicateInfo {
  isDuplicate: boolean;
  originalFilename?: string;
  originalId?: string;
}

export const SourcesPanel: React.FC<SourcesPanelProps> = ({
  documents,
  selectedDocIds,
  onToggleDoc,
  onSelectAll,
  onDeselectDoc,
  onCloseDrawer,
  isDrawer = false,
  isCollapsed = false,
  onToggleCollapse,
}) => {
  const [searchQuery, setSearchQuery] = useState('');

  // Map duplicate documents by content_hash (or fallback to identical file_size + page_count)
  const duplicatesMap = useMemo(() => {
    const map = new Map<string, DuplicateInfo>();
    const seenHashes = new Map<string, DocumentItem>();
    const seenSizes = new Map<string, DocumentItem>();

    for (const doc of documents) {
      if (doc.content_hash) {
        if (seenHashes.has(doc.content_hash)) {
          const orig = seenHashes.get(doc.content_hash)!;
          map.set(doc.id, {
            isDuplicate: true,
            originalFilename: orig.filename,
            originalId: orig.id,
          });
        } else {
          seenHashes.set(doc.content_hash, doc);
          map.set(doc.id, { isDuplicate: false });
        }
      } else {
        // Fallback for identical files when content_hash not populated
        const sizeKey = `${doc.file_size}_${doc.page_count}`;
        if (seenSizes.has(sizeKey)) {
          const orig = seenSizes.get(sizeKey)!;
          map.set(doc.id, {
            isDuplicate: true,
            originalFilename: orig.filename,
            originalId: orig.id,
          });
        } else {
          seenSizes.set(sizeKey, doc);
          map.set(doc.id, { isDuplicate: false });
        }
      }
    }
    return map;
  }, [documents]);

  const filteredDocs = useMemo(() => {
    if (!searchQuery.trim()) return documents;
    const q = searchQuery.toLowerCase();
    return documents.filter((d) => d.filename.toLowerCase().includes(q));
  }, [documents, searchQuery]);

  const allSelected = documents.length > 0 && selectedDocIds.length === documents.length;

  // Render Collapsed Strip view
  if (isCollapsed && !isDrawer) {
    return (
      <div className="flex flex-col items-center justify-between h-full py-3.5 px-1 bg-paper-surface select-none">
        <div className="flex flex-col items-center gap-3">
          <button
            type="button"
            onClick={onToggleCollapse}
            aria-label="Expand Sources panel"
            title="Expand Sources panel"
            className="p-2 rounded-xl bg-reading-primary/10 text-reading-primary hover:bg-reading-primary/20 transition-colors flex flex-col items-center gap-1 shadow-xs"
          >
            <Layers className="w-4 h-4" />
            <span className="text-[10px] font-mono font-bold">
              {selectedDocIds.length}
            </span>
          </button>

          {/* Vertical Dots for selected documents */}
          <div className="flex flex-col items-center gap-1.5 mt-2 overflow-y-auto max-h-[60vh] py-1">
            {documents
              .filter((d) => selectedDocIds.includes(d.id))
              .map((doc, idx) => {
                const ink = getPaperInk(doc.filename || doc.id, idx);
                const initial = getPaperInitial(doc.filename);
                return (
                  <span
                    key={doc.id}
                    className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white shadow-xs cursor-pointer hover:scale-110 transition-transform"
                    style={{ backgroundColor: ink.hex }}
                    title={doc.filename}
                    onClick={onToggleCollapse}
                  >
                    {initial}
                  </span>
                );
              })}
          </div>
        </div>

        <button
          type="button"
          onClick={onToggleCollapse}
          aria-label="Expand Sources panel"
          title="Expand Sources panel"
          className="p-1.5 rounded-lg text-ink-muted hover:text-ink hover:bg-paper-raised transition-colors"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full min-w-0 bg-paper-surface select-none">
      {/* Header Bar */}
      <div className="p-3 sm:p-4 border-b border-border-hairline bg-paper-surface flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-reading-primary shrink-0" />
          <span className="text-xs font-semibold uppercase tracking-wider text-ink font-mono">
            Sources
          </span>
          <Badge variant="outline" size="sm">
            {selectedDocIds.length} of {documents.length} selected
          </Badge>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onSelectAll}
            className="text-[11px] font-mono text-reading-primary hover:underline transition-colors"
          >
            {allSelected ? 'Deselect All' : 'Select All'}
          </button>

          {!isDrawer && onToggleCollapse && (
            <button
              type="button"
              onClick={onToggleCollapse}
              aria-label="Collapse Sources panel"
              title="Collapse Sources panel"
              className="p-1 rounded-md text-ink-muted hover:text-ink hover:bg-paper-raised transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
          )}

          {isDrawer && onCloseDrawer && (
            <button
              type="button"
              onClick={onCloseDrawer}
              aria-label="Close Scope Sources"
              className="p-1 rounded-md text-ink-muted hover:text-ink hover:bg-paper-raised transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Search Input Filter */}
      {documents.length > 2 && (
        <div className="px-3 py-2 border-b border-border-subtle shrink-0">
          <div className="relative flex items-center">
            <Search className="w-3.5 h-3.5 text-ink-muted absolute left-2.5 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter papers by title..."
              className="w-full pl-8 pr-2.5 py-1 text-xs bg-paper-bg border border-border-hairline rounded-md text-ink placeholder:text-ink-muted focus:outline-none focus:ring-1 focus:ring-reading-primary"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-2 text-ink-muted hover:text-ink"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Paper Cards List */}
      <div className="p-2 sm:p-3 overflow-y-auto flex-1 space-y-2 min-h-0">
        {documents.length === 0 ? (
          <div className="text-center p-6 text-xs text-ink-muted font-sans">
            No completed documents in library. Upload a PDF first.
          </div>
        ) : filteredDocs.length === 0 ? (
          <div className="text-center p-6 text-xs text-ink-muted font-sans">
            No papers match "{searchQuery}"
          </div>
        ) : (
          filteredDocs.map((doc, idx) => {
            const isSelected = selectedDocIds.includes(doc.id);
            const ink = getPaperInk(doc.filename || doc.id, idx);
            const initial = getPaperInitial(doc.filename);
            const dupInfo = duplicatesMap.get(doc.id);

            return (
              <div
                key={doc.id}
                className={`group relative p-2.5 rounded-lg border transition-all ${
                  isSelected
                    ? 'bg-reading-primary/[0.04] border-reading-primary/40 shadow-xs ring-1 ring-reading-primary/10'
                    : 'bg-paper-surface hover:bg-paper-raised border-border-hairline opacity-75'
                }`}
              >
                <div
                  className="flex items-start gap-2.5 cursor-pointer"
                  onClick={() => onToggleDoc(doc.id)}
                >
                  {/* Selection Checkbox */}
                  <button
                    type="button"
                    aria-label={`Select ${doc.filename}`}
                    className="mt-0.5 text-reading-primary focus:outline-none shrink-0"
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggleDoc(doc.id);
                    }}
                  >
                    {isSelected ? (
                      <CheckSquare className="w-4 h-4 fill-reading-primary/15 text-reading-primary" />
                    ) : (
                      <Square className="w-4 h-4 text-ink-muted" />
                    )}
                  </button>

                  {/* Deterministic Paper Initial & Ink Dot */}
                  <span
                    className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white shrink-0 mt-0.5 shadow-xs"
                    style={{ backgroundColor: ink.hex }}
                    title={`Paper Ink: ${ink.name}`}
                  >
                    {initial}
                  </span>

                  {/* Title and Metadata */}
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-xs font-medium text-ink leading-tight">
                      {doc.filename}
                    </div>

                    <div className="flex items-center gap-2 text-[10px] text-ink-muted font-mono mt-1">
                      <span>{doc.page_count} pp</span>
                      <span>&bull;</span>
                      <span>{doc.chunk_count} chunks</span>
                      <span>&bull;</span>
                      <span className="text-reading-primary capitalize font-medium">{doc.status}</span>
                    </div>
                  </div>
                </div>

                {/* Duplicate Badge & Deselect Action */}
                {dupInfo?.isDuplicate && (
                  <div className="mt-2 pt-2 border-t border-border-subtle flex items-center justify-between text-[11px] font-sans">
                    <div className="flex items-center gap-1.5 text-reading-warning min-w-0">
                      <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                      <span className="truncate">
                        Same file as <span className="font-medium underline">{dupInfo.originalFilename}</span>
                      </span>
                    </div>

                    {isSelected && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (onDeselectDoc) {
                            onDeselectDoc(doc.id);
                          } else {
                            onToggleDoc(doc.id);
                          }
                        }}
                        className="px-2 py-0.5 text-[10px] font-mono bg-reading-warning/10 hover:bg-reading-warning/20 text-reading-warning rounded border border-reading-warning/30 transition-colors shrink-0 ml-1.5"
                      >
                        Deselect copy
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Scope Footer Summary */}
      <div className="p-3 border-t border-border-hairline bg-paper-surface text-xs font-mono text-ink-muted flex items-center justify-between shrink-0">
        <span>Active Scope:</span>
        <span className="font-semibold text-ink">
          {selectedDocIds.length} {selectedDocIds.length === 1 ? 'paper' : 'papers'}
        </span>
      </div>
    </div>
  );
};
