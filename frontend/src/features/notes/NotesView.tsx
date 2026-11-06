import React, { useState, useEffect } from 'react';
import {
  BookMarked,
  Download,
  Trash2,
  Edit3,
  Copy,
  Check,
  ChevronLeft,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ResearchNoteItem } from '../../types';
import { api } from '../../services/api';

export const NotesView: React.FC = () => {
  const [notes, setNotes] = useState<ResearchNoteItem[]>([]);
  const [selectedNote, setSelectedNote] = useState<ResearchNoteItem | null>(null);
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [editTitle, setEditTitle] = useState<string>('');
  const [editContent, setEditContent] = useState<string>('');
  const [copied, setCopied] = useState<boolean>(false);
  const [showMobileList, setShowMobileList] = useState<boolean>(true);

  useEffect(() => {
    loadNotes();
  }, []);

  const loadNotes = async () => {
    try {
      const data = await api.listNotes();
      setNotes(data.items);
      if (data.items.length > 0 && !selectedNote) {
        setSelectedNote(data.items[0]);
      }
    } catch (err) {
      console.error('Failed to load notes:', err);
    }
  };

  const handleSelectNote = (note: ResearchNoteItem) => {
    setSelectedNote(note);
    setIsEditing(false);
    setShowMobileList(false);
  };

  const handleStartEdit = () => {
    if (!selectedNote) return;
    setEditTitle(selectedNote.title);
    setEditContent(selectedNote.content);
    setIsEditing(true);
  };

  const handleSaveEdit = async () => {
    if (!selectedNote) return;
    try {
      setSelectedNote({
        ...selectedNote,
        title: editTitle,
        content: editContent,
      });
      setIsEditing(false);
      loadNotes();
    } catch (err: any) {
      alert(`Failed to save edit: ${err.message}`);
    }
  };

  const handleDelete = async (noteId: string) => {
    if (!window.confirm('Are you sure you want to delete this research note?')) return;
    try {
      await api.deleteNote(noteId);
      const remaining = notes.filter((n) => n.id !== noteId);
      setNotes(remaining);
      setSelectedNote(remaining.length > 0 ? remaining[0] : null);
      if (remaining.length === 0) {
        setShowMobileList(true);
      }
    } catch (err: any) {
      alert(`Deletion failed: ${err.message}`);
    }
  };

  const handleExportMarkdown = async () => {
    if (!selectedNote) return;
    try {
      const exportData = await api.exportNote(selectedNote.id);
      const blob = new Blob([exportData.markdown_content], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = exportData.filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(`Export failed: ${err.message}`);
    }
  };

  const handleCopy = () => {
    if (!selectedNote) return;
    navigator.clipboard.writeText(selectedNote.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex flex-col md:flex-row h-full w-full overflow-hidden bg-parchment-50">
      {/* Left Column: Notes List (Desktop permanent, Mobile toggleable) */}
      <div
        className={`${
          showMobileList ? 'flex' : 'hidden md:flex'
        } w-full md:w-80 bg-white border-r border-parchment-300 flex-col shrink-0 h-full min-w-0`}
      >
        <div className="p-3 sm:p-4 border-b border-parchment-200 bg-parchment-100 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ink-700 font-mono">
            <BookMarked className="w-4 h-4 text-navy-800 shrink-0" />
            <span>Research Notes ({notes.length})</span>
          </div>
        </div>

        <div className="p-2 sm:p-3 overflow-y-auto flex-1 space-y-1.5 min-h-0">
          {notes.length === 0 ? (
            <div className="p-8 text-center text-xs text-ink-400">
              No notes saved yet. Save an answer in the Research Workspace to view it here.
            </div>
          ) : (
            notes.map((note) => {
              const isSelected = selectedNote?.id === note.id;
              return (
                <div
                  key={note.id}
                  onClick={() => handleSelectNote(note)}
                  className={`p-2.5 sm:p-3 rounded-lg border cursor-pointer text-xs transition-all ${
                    isSelected
                      ? 'bg-navy-50/70 border-navy-300 text-navy-950 font-medium shadow-xs'
                      : 'bg-white hover:bg-parchment-50 border-parchment-200 text-ink-700'
                  }`}
                >
                  <h4 className="font-serif font-bold text-ink-950 truncate mb-1">
                    {note.title}
                  </h4>
                  <p className="text-ink-500 line-clamp-2 leading-relaxed">
                    {note.content}
                  </p>
                  <div className="mt-2 text-[10px] font-mono text-ink-400">
                    {new Date(note.updated_at).toLocaleDateString()} • {note.source_citations?.length || 0} citations
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Right Column: Note Viewer & Editor */}
      <div
        className={`${
          !showMobileList ? 'flex' : 'hidden md:flex'
        } flex-1 min-w-0 min-h-0 flex-col h-full overflow-hidden bg-white`}
      >
        {selectedNote ? (
          <>
            {/* Header Toolbar */}
            <div className="px-4 sm:px-8 py-3 sm:py-4 border-b border-parchment-200 bg-parchment-50 flex flex-wrap items-center justify-between gap-3 shrink-0">
              <div className="flex items-center gap-2 min-w-0 flex-1">
                {/* Mobile Back Button to Notes List */}
                <button
                  type="button"
                  onClick={() => setShowMobileList(true)}
                  className="md:hidden p-1.5 rounded-lg text-ink-700 hover:bg-parchment-200"
                  aria-label="Back to Notes list"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <div className="min-w-0 flex-1">
                  <h2 className="text-base sm:text-lg font-serif font-bold text-ink-950 truncate">
                    {isEditing ? 'Editing Note' : selectedNote.title}
                  </h2>
                  <span className="text-[10px] sm:text-[11px] font-mono text-ink-500 block truncate">
                    Last updated {new Date(selectedNote.updated_at).toLocaleString()}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
                {!isEditing && (
                  <button
                    type="button"
                    onClick={handleStartEdit}
                    className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-parchment-300 hover:bg-parchment-100 text-ink-700 text-xs font-medium transition-colors"
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline">Edit</span>
                  </button>
                )}

                <button
                  type="button"
                  onClick={handleCopy}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-parchment-300 hover:bg-parchment-100 text-ink-700 text-xs font-medium transition-colors"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-forest-600" /> : <Copy className="w-3.5 h-3.5" />}
                  <span className="hidden sm:inline">{copied ? 'Copied' : 'Copy'}</span>
                </button>

                <button
                  type="button"
                  onClick={handleExportMarkdown}
                  className="flex items-center gap-1 px-2.5 sm:px-3 py-1.5 rounded-lg bg-navy-800 hover:bg-navy-900 text-white text-xs font-medium shadow-subtle transition-all"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Export .md</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleDelete(selectedNote.id)}
                  className="p-1.5 rounded-lg text-ink-400 hover:text-red-700 hover:bg-red-50 transition-colors"
                  title="Delete Note"
                  aria-label="Delete Note"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Note Content Area */}
            <div className="p-4 sm:p-8 overflow-y-auto flex-1 max-w-3xl space-y-6">
              {isEditing ? (
                <div className="space-y-4">
                  <input
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    className="w-full px-3 py-2 text-base font-serif font-bold border border-parchment-300 rounded-lg text-ink-950 focus:outline-hidden focus:ring-1 focus:ring-navy-600"
                  />
                  <textarea
                    rows={12}
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    className="w-full p-3 sm:p-4 text-xs font-mono border border-parchment-300 rounded-lg text-ink-900 focus:outline-hidden focus:ring-1 focus:ring-navy-600"
                  />
                  <div className="flex gap-2 justify-end">
                    <button
                      type="button"
                      onClick={() => setIsEditing(false)}
                      className="px-4 py-2 text-xs font-medium text-ink-700 hover:bg-parchment-100 rounded-lg"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleSaveEdit}
                      className="px-4 py-2 text-xs font-medium bg-navy-800 text-white rounded-lg"
                    >
                      Save Changes
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="prose prose-sm max-w-none text-xs leading-relaxed font-serif text-ink-900 break-words">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {selectedNote.content}
                    </ReactMarkdown>
                  </div>

                  {selectedNote.source_citations && selectedNote.source_citations.length > 0 && (
                    <div className="pt-6 border-t border-parchment-200 space-y-3">
                      <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-navy-800">
                        Preserved Source References & Excerpts
                      </h3>
                      <div className="space-y-2">
                        {selectedNote.source_citations.map((cite, idx) => (
                          <div
                            key={idx}
                            className="p-3 bg-parchment-50 border border-parchment-200 rounded-lg text-xs space-y-1 break-words"
                          >
                            <div className="flex items-center gap-2 font-mono font-semibold text-navy-950">
                              <span>[{cite.citation_id}]</span>
                              <span className="truncate">{cite.filename}</span>
                              <span className="text-ink-400">
                                (Page {cite.page_numbers?.join(', ') || 1})
                              </span>
                            </div>
                            <p className="text-ink-600 font-serif italic text-[11px] break-words">
                              "{cite.excerpt}"
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-center p-8 text-ink-400 text-xs">
            <BookMarked className="w-10 h-10 opacity-30 mb-2" />
            <p>Select a research note from the left sidebar to read or export.</p>
          </div>
        )}
      </div>
    </div>
  );
};
