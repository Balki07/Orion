import React, { useState, useEffect, useRef } from 'react';
import {
  Compass,
  Send,
  BookOpen,
  Copy,
  Check,
  BookmarkPlus,
  AlertTriangle,
  Clock,
  Sparkles,
  FileText,
  Layers,
  ChevronRight,
  Info,
  Loader2,
  X,
  ExternalLink,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { DocumentItem, CitationItem, ChatMessageItem, ClaimItem } from '../../types';
import { api } from '../../services/api';
import { CitationChip } from '../../components/common/CitationChip';
import { DocumentDetailModal } from '../documents/DocumentDetailModal';

export const ResearchWorkspace: React.FC = () => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [inputQuestion, setInputQuestion] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [activeCitation, setActiveCitation] = useState<CitationItem | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [savedNoteId, setSavedNoteId] = useState<string | null>(null);
  const [inspectDoc, setInspectDoc] = useState<DocumentItem | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadDocuments();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const loadDocuments = async () => {
    try {
      const data = await api.listDocuments({ status: 'completed' });
      setDocuments(data.items);
      // Default to all completed documents
      if (data.items.length > 0 && selectedDocIds.length === 0) {
        setSelectedDocIds(data.items.map((d) => d.id));
      }
    } catch (err) {
      console.error('Failed to load documents for workspace:', err);
    }
  };

  const handleToggleDoc = (docId: string) => {
    setSelectedDocIds((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    );
  };

  const handleSelectAll = () => {
    if (selectedDocIds.length === documents.length) {
      setSelectedDocIds([]);
    } else {
      setSelectedDocIds(documents.map((d) => d.id));
    }
  };

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputQuestion.trim() || isLoading) return;

    const question = inputQuestion.trim();
    setInputQuestion('');

    // Append user message
    const userMsg: ChatMessageItem = {
      id: `usr_${Date.now()}`,
      session_id: 'default',
      role: 'user',
      content: question,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const response = await api.askQuestion({
        question,
        document_ids: selectedDocIds.length > 0 ? selectedDocIds : undefined,
        top_k: 8,
      });

      const assistantMsg: ChatMessageItem = {
        id: response.message_id || `asst_${Date.now()}`,
        session_id: 'default',
        role: 'assistant',
        content: response.answer,
        claims: response.claims,
        citations: response.citations,
        insufficient_evidence: response.insufficient_evidence,
        warnings: response.warnings,
        latency_ms: response.latency_ms,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMsg]);

      // If citations exist, activate the first one in the right panel
      if (response.citations && response.citations.length > 0) {
        setActiveCitation(response.citations[0]);
      } else {
        setActiveCitation(null);
      }
      setIsLoading(false);
    } catch (err: any) {
      const errorMsg: ChatMessageItem = {
        id: `err_${Date.now()}`,
        session_id: 'default',
        role: 'assistant',
        content: `Error generating research answer: ${err.message}`,
        insufficient_evidence: true,
        warnings: [err.message],
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
      setIsLoading(false);
    }
  };

  const handleCopyAnswer = (content: string, id: string) => {
    navigator.clipboard.writeText(content);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleSaveAsNote = async (msg: ChatMessageItem) => {
    try {
      await api.createNote({
        title: `Research Synthesis: ${msg.content.slice(0, 50)}...`,
        content: msg.content,
        source_citations: msg.citations,
      });
      setSavedNoteId(msg.id);
      setTimeout(() => setSavedNoteId(null), 2500);
    } catch (err: any) {
      alert(`Failed to save note: ${err.message}`);
    }
  };

  const openFullDocument = (documentId: string) => {
    const doc = documents.find((d) => d.id === documentId);
    if (doc) setInspectDoc(doc);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-parchment-50">
      {/* LEFT PANE: Selected Research Sources (260px) */}
      <div className="w-72 bg-white border-r border-parchment-300 flex flex-col shrink-0">
        <div className="p-4 border-b border-parchment-200 bg-parchment-100 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ink-700 font-mono">
            <Layers className="w-4 h-4 text-navy-800" />
            <span>Scope Sources ({selectedDocIds.length}/{documents.length})</span>
          </div>
          <button
            type="button"
            onClick={handleSelectAll}
            className="text-[11px] font-mono text-navy-800 hover:underline"
          >
            {selectedDocIds.length === documents.length ? 'Deselect All' : 'Select All'}
          </button>
        </div>

        <div className="p-3 overflow-y-auto flex-1 space-y-1.5">
          {documents.length === 0 ? (
            <div className="text-center p-6 text-xs text-ink-400">
              No completed documents yet. Upload a PDF first.
            </div>
          ) : (
            documents.map((doc) => {
              const isSelected = selectedDocIds.includes(doc.id);
              return (
                <div
                  key={doc.id}
                  onClick={() => handleToggleDoc(doc.id)}
                  className={`flex items-start gap-2.5 p-2.5 rounded-lg border cursor-pointer text-xs transition-all ${
                    isSelected
                      ? 'bg-navy-50/70 border-navy-300 text-navy-950 font-medium'
                      : 'bg-white hover:bg-parchment-50 border-parchment-200 text-ink-600'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => {}}
                    className="mt-0.5 rounded text-navy-800 focus:ring-navy-600"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium">{doc.filename}</div>
                    <div className="text-[10px] text-ink-400 font-mono mt-0.5">
                      {doc.page_count} pp • {doc.chunk_count} chunks
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* CENTER PANE: Conversation & Evidence-Grounded Answers (flex-1) */}
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-parchment-50">
        {/* Workspace Subheader */}
        <div className="px-6 py-3 border-b border-parchment-200 bg-white flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <Compass className="w-4 h-4 text-navy-800" />
            <span className="font-semibold text-ink-900 font-serif">Evidence-Grounded Research Session</span>
          </div>
          <div className="flex items-center gap-4 text-ink-500 font-mono text-[11px]">
            <span>Model: Gemini 1.5 Flash</span>
            <span>Embedding: BGE-small-en-v1.5</span>
          </div>
        </div>

        {/* Message Stream */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center max-w-md mx-auto space-y-4">
              <div className="w-14 h-14 rounded-2xl bg-navy-100 flex items-center justify-center text-navy-800 shadow-subtle">
                <Sparkles className="w-7 h-7" />
              </div>
              <h2 className="text-lg font-serif font-bold text-ink-900">
                Ask anything about your research papers
              </h2>
              <p className="text-xs text-ink-600 leading-relaxed">
                ORION answers strictly from retrieved passages, provides verified page citations, classifies supporting claims, and abstains when evidence is missing.
              </p>
              <div className="w-full pt-4 space-y-2 text-left">
                <div className="text-[11px] font-mono text-ink-400 uppercase tracking-wider">Example queries:</div>
                <button
                  type="button"
                  onClick={() => setInputQuestion('What is the computational complexity of self-attention per layer?')}
                  className="w-full p-2.5 rounded-lg border border-parchment-300 bg-white hover:bg-parchment-100 text-xs text-ink-800 text-left transition-colors"
                >
                  "What is the computational complexity of self-attention per layer?"
                </button>
                <button
                  type="button"
                  onClick={() => setInputQuestion('What BLEU scores and benchmark datasets were evaluated?')}
                  className="w-full p-2.5 rounded-lg border border-parchment-300 bg-white hover:bg-parchment-100 text-xs text-ink-800 text-left transition-colors"
                >
                  "What BLEU scores and benchmark datasets were evaluated?"
                </button>
              </div>
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
              >
                {msg.role === 'user' ? (
                  <div className="max-w-xl bg-navy-800 text-white rounded-2xl rounded-tr-xs px-4 py-3 text-sm shadow-subtle">
                    {msg.content}
                  </div>
                ) : (
                  <div className="max-w-2xl bg-white border border-parchment-300 rounded-2xl rounded-tl-xs p-5 shadow-xs space-y-4 text-ink-900">
                    {/* Abstention Alert */}
                    {msg.insufficient_evidence && (
                      <div className="flex items-start gap-2.5 p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 text-xs">
                        <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
                        <div>
                          <div className="font-semibold text-amber-800">Insufficient Evidence Detected</div>
                          <div className="text-amber-700 mt-0.5">
                            The provided documents do not contain evidence to substantiate this answer without speculation.
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Formatted Answer Markdown */}
                    <div className="prose prose-sm max-w-none text-xs leading-relaxed font-serif text-ink-950">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.content}
                      </ReactMarkdown>
                    </div>

                    {/* Citations Row */}
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="pt-3 border-t border-parchment-200">
                        <div className="text-[11px] font-mono text-ink-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                          <BookOpen className="w-3.5 h-3.5 text-navy-700" />
                          <span>Verified Page Citations ({msg.citations.length})</span>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {msg.citations.map((cite) => (
                            <CitationChip
                              key={cite.citation_id}
                              citation={cite}
                              isActive={activeCitation?.citation_id === cite.citation_id}
                              onClick={(c) => setActiveCitation(c)}
                            />
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Claims Breakdown */}
                    {msg.claims && msg.claims.length > 0 && (
                      <details className="text-[11px] text-ink-600 bg-parchment-50 rounded-lg p-2.5 border border-parchment-200 cursor-pointer">
                        <summary className="font-mono font-medium text-ink-700 hover:text-navy-800">
                          Inspect Claim Support Status ({msg.claims.length} claims)
                        </summary>
                        <div className="mt-2 space-y-1.5">
                          {msg.claims.map((claim, idx) => (
                            <div key={idx} className="flex items-start gap-2 pl-2 border-l-2 border-forest-500 py-0.5">
                              <span className="capitalize px-1.5 py-0.2 rounded text-[10px] font-mono bg-forest-100 text-forest-800">
                                {claim.support_status}
                              </span>
                              <span className="flex-1 text-ink-800">{claim.text}</span>
                            </div>
                          ))}
                        </div>
                      </details>
                    )}

                    {/* Footer Actions & Latency */}
                    <div className="pt-2 flex items-center justify-between text-[11px] text-ink-400 font-mono">
                      <div className="flex items-center gap-3">
                        <button
                          type="button"
                          onClick={() => handleCopyAnswer(msg.content, msg.id)}
                          className="flex items-center gap-1 hover:text-ink-800 transition-colors"
                        >
                          {copiedId === msg.id ? <Check className="w-3.5 h-3.5 text-forest-600" /> : <Copy className="w-3.5 h-3.5" />}
                          <span>{copiedId === msg.id ? 'Copied' : 'Copy'}</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => handleSaveAsNote(msg)}
                          className="flex items-center gap-1 hover:text-ink-800 transition-colors"
                        >
                          <BookmarkPlus className="w-3.5 h-3.5" />
                          <span>{savedNoteId === msg.id ? 'Saved to Notes!' : 'Save Note'}</span>
                        </button>
                      </div>

                      {msg.latency_ms?.total && (
                        <div className="flex items-center gap-1" title="End-to-end latency">
                          <Clock className="w-3 h-3" />
                          <span>{msg.latency_ms.total.toFixed(0)} ms</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))
          )}

          {isLoading && (
            <div className="flex items-center gap-2 p-4 bg-white rounded-2xl border border-parchment-300 text-xs text-ink-600 max-w-sm animate-pulse">
              <Loader2 className="w-4 h-4 text-navy-700 animate-spin" />
              <span>Retrieving hybrid evidence & validating citations...</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Query Input Bar */}
        <div className="p-4 bg-white border-t border-parchment-300">
          <form onSubmit={handleAsk} className="flex items-center gap-3 max-w-3xl mx-auto">
            <input
              type="text"
              value={inputQuestion}
              onChange={(e) => setInputQuestion(e.target.value)}
              placeholder="Ask a technical or research question..."
              className="flex-1 px-4 py-2.5 text-sm bg-parchment-50 border border-parchment-300 rounded-xl text-ink-950 focus:outline-hidden focus:ring-1 focus:ring-navy-700"
            />
            <button
              type="submit"
              disabled={!inputQuestion.trim() || isLoading}
              className="px-5 py-2.5 bg-navy-800 hover:bg-navy-900 disabled:opacity-50 text-white rounded-xl shadow-subtle flex items-center gap-2 text-sm font-medium transition-all"
            >
              <span>Verify</span>
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>

      {/* RIGHT PANE: Citation Evidence & Page Excerpt Inspector (360px) */}
      <div className="w-96 bg-white border-l border-parchment-300 flex flex-col shrink-0">
        <div className="p-4 border-b border-parchment-200 bg-parchment-100 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ink-700 font-mono">
            <BookOpen className="w-4 h-4 text-navy-800" />
            <span>Citation Evidence Inspector</span>
          </div>
          {activeCitation && (
            <button
              type="button"
              onClick={() => setActiveCitation(null)}
              className="p-1 rounded text-ink-400 hover:text-ink-700 hover:bg-parchment-200"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        <div className="p-5 overflow-y-auto flex-1 space-y-4">
          {activeCitation ? (
            <div className="space-y-4">
              <div className="p-3 bg-navy-50/70 border border-navy-200 rounded-lg">
                <div className="text-[10px] font-mono uppercase text-navy-700 font-bold">
                  Citation Provenance Target
                </div>
                <div className="text-sm font-serif font-bold text-ink-950 mt-1 truncate">
                  {activeCitation.filename}
                </div>
                <div className="text-xs font-mono text-ink-600 mt-0.5">
                  Verified Page: {activeCitation.page_numbers.join(', ')}
                </div>
              </div>

              <div className="space-y-2">
                <div className="text-xs font-mono uppercase text-ink-500 font-medium">
                  Retrieved Supporting Excerpt
                </div>
                <div className="p-4 bg-parchment-50 border border-parchment-300 rounded-lg text-xs leading-relaxed font-serif text-ink-900 shadow-inner">
                  "{activeCitation.excerpt}"
                </div>
              </div>

              <div className="p-3 bg-parchment-100 rounded-lg border border-parchment-200 text-[11px] font-mono text-ink-600 space-y-1">
                <div>Citation ID: <span className="font-semibold text-ink-900">{activeCitation.citation_id}</span></div>
                <div>Document ID: <span className="text-ink-500">{activeCitation.document_id}</span></div>
                <div>Chunk IDs: <span className="text-ink-500">{activeCitation.chunk_ids.join(', ')}</span></div>
              </div>

              <button
                type="button"
                onClick={() => openFullDocument(activeCitation.document_id)}
                className="w-full flex items-center justify-center gap-2 py-2 px-3 bg-parchment-200 hover:bg-parchment-300 text-ink-800 rounded-lg text-xs font-medium transition-colors"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                <span>Open Full Document Page Inspector</span>
              </button>
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 text-xs text-ink-400 space-y-2">
              <BookOpen className="w-8 h-8 opacity-40" />
              <p>Click on any citation chip in an answer to inspect its original page text, verified provenance, and exact excerpts here.</p>
            </div>
          )}
        </div>
      </div>

      {/* Full Document Inspector Modal */}
      <DocumentDetailModal
        document={inspectDoc}
        onClose={() => setInspectDoc(null)}
      />
    </div>
  );
};
