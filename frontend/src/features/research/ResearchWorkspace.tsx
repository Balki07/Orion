import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Compass,
  Send,
  BookOpen,
  Copy,
  Check,
  BookmarkPlus,
  AlertTriangle,
  Clock,
  Layers,
  Loader2,
  X,
  ExternalLink,
  ShieldCheck,
  FileText,
  HelpCircle,
  Sparkles,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { DocumentItem, CitationItem, ChatMessageItem } from '../../types';
import { api } from '../../services/api';
import { DocumentDetailModal } from '../documents/DocumentDetailModal';
import { CitationChip } from '../../components/common/CitationChip';
import { SourcesPanel } from './SourcesPanel';
import { ScopeGuardPrompt } from './ScopeGuardPrompt';
import { EvidenceInspector } from './EvidenceInspector';
import { AnswerRenderer } from './AnswerRenderer';
import { GroundingStrip } from './GroundingStrip';
import { getResearchPreferences } from '../../utils/researchPreferences';
import { AbstentionBanner } from './AbstentionBanner';
import { AnswerActions } from './AnswerActions';
import { toast } from 'sonner';
import { getPaperInk, getPaperInitial } from '../../utils/paperInks';
import { Badge } from '../../components/ui/Badge';
import { Tooltip } from '../../components/ui/Tooltip';

export function getPlainFallbackBanner(msg: ChatMessageItem): string {
  if (msg.fallback_reason === 'UNAVAILABLE') {
    return 'Gemini is experiencing high demand (503). Answered using verified research literature directly';
  }
  if (msg.fallback_reason === 'QUOTA') {
    return 'Gemini daily limit reached, using basic mode';
  }
  if (msg.fallback_reason === 'BAD_KEY') {
    return 'Gemini key problem, using basic mode';
  }
  if (msg.fallback_reason === 'KEY_NOT_LOADED') {
    return 'Gemini key not configured, using basic mode';
  }
  if (msg.fallback_reason === 'MODEL_NOT_FOUND') {
    return 'Gemini model unavailable, using basic mode';
  }
  if (msg.fallback_reason === 'NETWORK') {
    return 'Network error connecting to Gemini, using basic mode';
  }
  if (msg.fallback_reason === 'OTHER') {
    return 'Gemini unavailable, using basic mode';
  }
  if (msg.warnings && msg.warnings.length > 0) {
    const w = msg.warnings.find(
      (item) =>
        item.includes('basic mode') ||
        item.toLowerCase().includes('fallback') ||
        item.toLowerCase().includes('limit') ||
        item.toLowerCase().includes('unavailable')
    );
    if (w) {
      return w
        .replace(/\(ClientError\)/gi, '')
        .replace(/\(JSONDecodeError\)/gi, '')
        .replace(/\(ServerError\)/gi, '')
        .replace(/\s+/g, ' ')
        .trim();
    }
  }
  return 'Gemini unavailable, using basic mode';
}

export const ResearchWorkspace: React.FC = () => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [inputQuestion, setInputQuestion] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [activeCitation, setActiveCitation] = useState<CitationItem | null>(null);
  const [activeAnswerCitations, setActiveAnswerCitations] = useState<CitationItem[]>([]);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [savedNoteId, setSavedNoteId] = useState<string | null>(null);
  const [isSavingNoteId, setIsSavingNoteId] = useState<string | null>(null);
  const [inspectDoc, setInspectDoc] = useState<DocumentItem | null>(null);
  const [inspectDocInitialPage, setInspectDocInitialPage] = useState<number>(1);
  const [scopeGuardDismissed, setScopeGuardDismissed] = useState<boolean>(false);

  // Sources Panel Collapsible state on Desktop
  const [isSourcesCollapsed, setIsSourcesCollapsed] = useState<boolean>(false);

  // Evidence Inspector Closed by default on Desktop & Mobile
  const [isEvidenceInspectorOpen, setIsEvidenceInspectorOpen] = useState<boolean>(false);

  // Responsive Drawer states for < 1200px viewports
  const [isSourcesDrawerOpen, setIsSourcesDrawerOpen] = useState<boolean>(false);
  const [isCitationDrawerOpen, setIsCitationDrawerOpen] = useState<boolean>(false);

  // Mobile / Narrow Tab Mode: 'sources' | 'conversation' | 'evidence'
  const [mobileTab, setMobileTab] = useState<'sources' | 'conversation' | 'evidence'>('conversation');

  const sourcesToggleRef = useRef<HTMLButtonElement>(null);
  const citationToggleRef = useRef<HTMLButtonElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [activeModel, setActiveModel] = useState<string>('gemini-3.5-flash-lite');

  const latestAssistantMsg = [...messages].reverse().find((m) => m.role === 'assistant');
  const currentModelLabel = latestAssistantMsg
    ? latestAssistantMsg.answer_path === 'deterministic_fallback'
      ? 'Deterministic mode'
      : latestAssistantMsg.model || activeModel
    : activeModel;

  const selectedDocuments = useMemo(() => {
    return documents.filter((d) => selectedDocIds.includes(d.id));
  }, [documents, selectedDocIds]);

  useEffect(() => {
    loadDocuments();
    api
      .getSettings()
      .then((s) => {
        if (s?.active_gemini_model) setActiveModel(s.active_gemini_model);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView?.({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Handle Escape key to close drawers or desktop inspector
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (isCitationDrawerOpen || isEvidenceInspectorOpen) {
          setIsCitationDrawerOpen(false);
          setIsEvidenceInspectorOpen(false);
          citationToggleRef.current?.focus();
        } else if (isSourcesDrawerOpen) {
          setIsSourcesDrawerOpen(false);
          sourcesToggleRef.current?.focus();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isCitationDrawerOpen, isEvidenceInspectorOpen, isSourcesDrawerOpen]);

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
    setScopeGuardDismissed(false);
  };

  const handleDeselectDoc = (docId: string) => {
    setSelectedDocIds((prev) => prev.filter((id) => id !== docId));
  };

  const handleSelectSingleDoc = (docId: string) => {
    setSelectedDocIds([docId]);
    setScopeGuardDismissed(false);
  };

  const handleSelectAll = () => {
    if (selectedDocIds.length === documents.length) {
      setSelectedDocIds([]);
    } else {
      setSelectedDocIds(documents.map((d) => d.id));
    }
    setScopeGuardDismissed(false);
  };

  const handleCitationClick = (citation: CitationItem, messageCitations?: CitationItem[]) => {
    setActiveCitation(citation);
    if (messageCitations && messageCitations.length > 0) {
      setActiveAnswerCitations(messageCitations);
    } else {
      const foundMsg = [...messages].reverse().find((m) =>
        m.citations?.some((c) => c.citation_id === citation.citation_id && c.document_id === citation.document_id)
      );
      if (foundMsg?.citations) {
        setActiveAnswerCitations(foundMsg.citations);
      } else {
        setActiveAnswerCitations([citation]);
      }
    }
    // Open Evidence Inspector and return space when closed
    setIsEvidenceInspectorOpen(true);
    setIsCitationDrawerOpen(true);
    setMobileTab('evidence');
  };

  const handleCloseSourcesDrawer = () => {
    setIsSourcesDrawerOpen(false);
    sourcesToggleRef.current?.focus();
  };

  const handleCloseCitationDrawer = () => {
    setIsCitationDrawerOpen(false);
    setIsEvidenceInspectorOpen(false);
    citationToggleRef.current?.focus();
  };

  const handleCloseDesktopEvidenceInspector = () => {
    setIsEvidenceInspectorOpen(false);
    setIsCitationDrawerOpen(false);
    citationToggleRef.current?.focus();
  };

  const executeAsk = async (question: string) => {
    if (!question.trim() || isLoading) return;

    setScopeGuardDismissed(false);

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
      const prefs = getResearchPreferences();
      const response = await api.askQuestion({
        question,
        document_ids: selectedDocIds.length > 0 ? selectedDocIds : undefined,
        top_k: prefs.defaultTopK || 8,
      });

      const assistantMsg: ChatMessageItem = {
        id: response.message_id || `asst_${Date.now()}`,
        session_id: 'default',
        role: 'assistant',
        content: response.answer,
        claims: response.claims,
        citations: response.citations,
        insufficient_evidence: response.insufficient_evidence,
        reason_code: response.reason_code,
        trace_id: response.trace_id,
        warnings: response.warnings,
        latency_ms: response.latency_ms,
        model: response.model,
        answer_path: response.answer_path,
        fallback_reason: response.fallback_reason,
        created_at: new Date().toISOString(),
      };

      if (response.model) {
        setActiveModel(response.model);
      }

      setMessages((prev) => [...prev, assistantMsg]);

      // If citations exist, preserve active citation but keep inspector closed until clicked
      if (response.citations && response.citations.length > 0) {
        setActiveCitation(response.citations[0]);
        setActiveAnswerCitations(response.citations);
      } else {
        setActiveCitation(null);
        setActiveAnswerCitations([]);
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

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputQuestion.trim() || isLoading) return;
    const question = inputQuestion.trim();
    setInputQuestion('');
    await executeAsk(question);
  };

  const handleCopyAnswer = (content: string, id: string) => {
    navigator.clipboard.writeText(content);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleSaveAsNote = async (msg: ChatMessageItem) => {
    try {
      setIsSavingNoteId(msg.id);
      const cleanSnippet = msg.content.replace(/^[#\s]+/, '').slice(0, 50);
      await api.createNote({
        title: `Research Synthesis: ${cleanSnippet}...`,
        content: msg.content,
        source_citations: msg.citations,
      });
      setSavedNoteId(msg.id);
      toast.success('Research synthesis saved to Notes');
      setTimeout(() => setSavedNoteId(null), 3000);
    } catch (err: any) {
      toast.error(`Failed to save note: ${err.message}`);
    } finally {
      setIsSavingNoteId(null);
    }
  };

  const openFullDocument = (documentId: string, pageNumber?: number) => {
    const doc = documents.find((d) => d.id === documentId);
    if (pageNumber) setInspectDocInitialPage(pageNumber);
    if (doc) setInspectDoc(doc);
  };

  return (
    <div className="flex h-full w-full overflow-hidden bg-paper-bg relative text-ink">
      {/* ======================================================== */}
      {/* 1. LEFT PANE: Sources Panel (Collapsible on Desktop) */}
      {/* ======================================================== */}
      <div
        id="desktop-sources-panel"
        aria-label="Scope Sources Panel"
        className={`hidden lg:flex ${
          isSourcesCollapsed ? 'w-14' : 'lg:w-64 xl:w-72'
        } shrink-0 bg-paper-surface border-r border-border-hairline flex-col h-full min-w-0 transition-all duration-200`}
      >
        <SourcesPanel
          documents={documents}
          selectedDocIds={selectedDocIds}
          onToggleDoc={handleToggleDoc}
          onSelectAll={handleSelectAll}
          onDeselectDoc={handleDeselectDoc}
          isCollapsed={isSourcesCollapsed}
          onToggleCollapse={() => setIsSourcesCollapsed(!isSourcesCollapsed)}
        />
      </div>

      {/* ======================================================== */}
      {/* 2. CENTER PANE: Claude-Inspired Conversation & Composer */}
      {/* ======================================================== */}
      <div className="flex-1 min-w-0 min-h-0 flex flex-col h-full overflow-hidden bg-paper-bg">
        {/* Workspace Top Header Bar */}
        <header className="px-4 sm:px-6 py-3 border-b border-border-hairline bg-paper-surface flex flex-wrap items-center justify-between gap-3 text-xs shrink-0 z-10">
          <div className="flex items-center gap-3 min-w-0">
            {/* Desktop Sources Expand button when collapsed */}
            {isSourcesCollapsed && (
              <button
                type="button"
                onClick={() => setIsSourcesCollapsed(false)}
                aria-label="Expand Sources panel"
                title="Expand Sources panel"
                className="hidden lg:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-border-hairline bg-paper-card hover:bg-paper-raised text-ink text-xs font-medium transition-colors"
              >
                <Layers className="w-4 h-4 text-reading-primary shrink-0" />
                <span>Sources</span>
                <span className="font-mono text-[11px] bg-reading-primary/10 text-reading-primary px-1.5 py-0.5 rounded font-bold border border-reading-primary/20">
                  {selectedDocIds.length}
                </span>
              </button>
            )}

            <div className="flex items-center gap-2 min-w-0">
              <span className="p-1.5 rounded-lg bg-reading-primary/10 text-reading-primary">
                <Compass className="w-4 h-4 shrink-0" />
              </span>
              <span className="font-serif font-semibold text-ink text-sm sm:text-base truncate">
                Evidence-Grounded Research Session
              </span>
            </div>
          </div>

          {/* Controls: Model Badge & Panel Toggles */}
          <div className="flex items-center gap-2.5">
            {/* Model / Mode Attribution Chip */}
            <div className="flex items-center gap-2 font-mono text-[11px]">
              <div
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border ${
                  latestAssistantMsg?.answer_path === 'deterministic_fallback'
                    ? 'bg-reading-warning-bg border-reading-warning/30 text-reading-warning'
                    : 'bg-paper-card border-border-hairline text-ink'
                }`}
              >
                <span
                  className={`w-2 h-2 rounded-full ${
                    latestAssistantMsg?.answer_path === 'deterministic_fallback'
                      ? 'bg-reading-warning'
                      : 'bg-reading-primary animate-pulse'
                  }`}
                />
                <span className="text-ink-muted">Model:</span>
                <span data-testid="header-model-label" className="font-semibold text-ink">
                  {currentModelLabel}
                </span>
              </div>
            </div>

            {/* Toggle Sources button for responsive viewports (< 1200px) */}
            <button
              ref={sourcesToggleRef}
              type="button"
              onClick={() => setIsSourcesDrawerOpen(true)}
              aria-label="Toggle Scope Sources panel"
              aria-expanded={isSourcesDrawerOpen}
              aria-controls="sources-drawer"
              className="flex lg:hidden items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-border-hairline bg-paper-card hover:bg-paper-raised text-ink text-xs font-medium transition-colors"
            >
              <Layers className="w-3.5 h-3.5 text-reading-primary shrink-0" />
              <span className="hidden sm:inline">Sources</span>
              <span className="font-mono text-[11px] bg-reading-primary/10 text-reading-primary px-1.5 py-0.5 rounded font-bold border border-reading-primary/20">
                {selectedDocIds.length}/{documents.length}
              </span>
            </button>

            {/* Toggle Evidence Inspector Button (Desktop & Mobile) */}
            <button
              ref={citationToggleRef}
              type="button"
              onClick={() => {
                const next = !(isEvidenceInspectorOpen || isCitationDrawerOpen);
                setIsEvidenceInspectorOpen(next);
                setIsCitationDrawerOpen(next);
              }}
              aria-label="Toggle Citation Evidence Inspector"
              aria-expanded={isEvidenceInspectorOpen || isCitationDrawerOpen}
              aria-controls="citation-drawer"
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all ${
                isEvidenceInspectorOpen || isCitationDrawerOpen
                  ? 'border-reading-primary/40 bg-reading-primary/10 text-reading-primary font-semibold shadow-xs'
                  : 'border-border-hairline bg-paper-card hover:bg-paper-raised text-ink'
              }`}
            >
              <BookOpen className="w-3.5 h-3.5 text-reading-primary shrink-0" />
              <span>Evidence</span>
              {activeCitation && (
                <span className="font-mono text-[10px] bg-reading-primary text-white px-1.5 py-0.5 rounded-full font-bold">
                  {String(activeCitation.citation_id).replace(/^cite:/i, '')}
                </span>
              )}
            </button>
          </div>
        </header>

        {/* Message Stream: Spacious, Independent Scroll, Claude-Style Centered */}
        <div className="flex-1 min-h-0 overflow-y-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6 scroll-smooth">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center max-w-xl mx-auto space-y-5 p-4 my-auto">
              <div className="w-14 h-14 rounded-2xl bg-reading-primary/10 border border-reading-primary/20 flex items-center justify-center text-reading-primary shadow-xs shrink-0">
                <Compass className="w-7 h-7" />
              </div>
              <div className="space-y-2">
                <h2 className="text-2xl sm:text-3xl font-serif font-semibold text-ink tracking-tight">
                  Academic Literature Research Room
                </h2>
                <p className="text-sm sm:text-[15px] text-ink-secondary leading-relaxed font-sans max-w-md mx-auto">
                  Every answer is grounded in retrieved passages from verified PDFs with exact page provenance. ORION abstains when evidence is insufficient.
                </p>
              </div>

              <div className="w-full pt-4 space-y-2.5 text-left">
                <div className="text-xs font-mono text-ink-muted uppercase tracking-wider px-1">
                  Example academic queries:
                </div>
                <button
                  type="button"
                  onClick={() => setInputQuestion('What is the computational complexity of self-attention per layer?')}
                  className="w-full p-3.5 rounded-xl border border-border-hairline bg-paper-card hover:bg-paper-raised hover:border-reading-primary/40 text-xs sm:text-sm text-ink text-left transition-all font-serif shadow-xs flex items-center justify-between group"
                >
                  <span>"What is the computational complexity of self-attention per layer?"</span>
                  <Sparkles className="w-3.5 h-3.5 text-reading-primary opacity-0 group-hover:opacity-100 transition-opacity shrink-0 ml-2" />
                </button>
                <button
                  type="button"
                  onClick={() => setInputQuestion('What BLEU scores and benchmark datasets were evaluated?')}
                  className="w-full p-3.5 rounded-xl border border-border-hairline bg-paper-card hover:bg-paper-raised hover:border-reading-primary/40 text-xs sm:text-sm text-ink text-left transition-all font-serif shadow-xs flex items-center justify-between group"
                >
                  <span>"What BLEU scores and benchmark datasets were evaluated?"</span>
                  <Sparkles className="w-3.5 h-3.5 text-reading-primary opacity-0 group-hover:opacity-100 transition-opacity shrink-0 ml-2" />
                </button>
              </div>
            </div>
          ) : (
            <div className="max-w-3xl lg:max-w-4xl mx-auto w-full space-y-6">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'} w-full`}
                >
                  {msg.role === 'user' ? (
                    <div className="max-w-2xl w-auto break-words bg-reading-primary text-white rounded-2xl rounded-tr-xs px-5 py-3.5 text-sm sm:text-base shadow-sm font-sans leading-relaxed">
                      {msg.content}
                    </div>
                  ) : (
                    <div className="w-full bg-paper-card border border-border-hairline rounded-2xl p-6 sm:p-7 shadow-paper space-y-5 text-ink break-words">
                      {/* 1. Calm Scholarly Abstention Banner */}
                      {msg.insufficient_evidence && (
                        <AbstentionBanner
                          insufficientEvidence={msg.insufficient_evidence}
                          reasonCode={msg.reason_code}
                          traceId={msg.trace_id}
                          onOpenSources={() => setIsSourcesDrawerOpen(true)}
                        />
                      )}

                      {/* 2. Model Fallback Warning Banner */}
                      {(msg.answer_path === 'deterministic_fallback' ||
                        (msg.warnings &&
                          msg.warnings.some(
                            (w) =>
                              w.toLowerCase().includes('fallback') ||
                              w.toLowerCase().includes('unavailable') ||
                              w.toLowerCase().includes('limit') ||
                              w.toLowerCase().includes('basic mode')
                          ))) && (
                        <div
                          data-testid="fallback-banner"
                          className="flex items-center gap-2 p-3 rounded-xl bg-reading-warning-bg border border-reading-warning/30 text-xs text-ink font-sans"
                        >
                          <AlertTriangle className="w-4 h-4 text-reading-warning shrink-0" />
                          <span>{getPlainFallbackBanner(msg)}</span>
                        </div>
                      )}

                      {/* 3. Claim Grounding Strip (Rendered strictly from trustworthy API claim-support data) */}
                      {msg.claims && msg.claims.length > 0 && (
                        <GroundingStrip
                          claims={msg.claims}
                          citations={msg.citations}
                          onCitationClick={handleCitationClick}
                        />
                      )}

                      {/* 4. Scholarly Formatted Answer with Inline Interactive Citation Chips */}
                      <AnswerRenderer
                        content={msg.content}
                        citations={msg.citations}
                        activeCitationId={activeCitation?.citation_id}
                        onCitationClick={(cite) => handleCitationClick(cite, msg.citations)}
                      />

                      {/* 5. Verified Citations Reference Row */}
                      {msg.citations && msg.citations.length > 0 && (
                        <div className="pt-4 border-t border-border-hairline">
                          <div className="text-xs font-mono text-ink-muted uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                            <BookOpen className="w-3.5 h-3.5 text-reading-primary shrink-0" />
                            <span>Verified Page Citations ({msg.citations.length})</span>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {msg.citations.map((cite) => (
                              <CitationChip
                                key={cite.citation_id}
                                citation={cite}
                                isActive={activeCitation?.citation_id === cite.citation_id}
                                onClick={(cite) => handleCitationClick(cite, msg.citations)}
                              />
                            ))}
                          </div>
                        </div>
                      )}

                      {/* 6. Answer Actions Bar (Copy with Citations, Save to Notes, Regenerate, Model Attribution) */}
                      <AnswerActions
                        content={msg.content}
                        citations={msg.citations}
                        model={msg.model}
                        answerPath={msg.answer_path}
                        fallbackReason={msg.fallback_reason}
                        latencyMs={msg.latency_ms}
                        onRegenerate={() => {
                          const lastUser = [...messages].reverse().find((m) => m.role === 'user');
                          if (lastUser) executeAsk(lastUser.content);
                        }}
                        onSaveToNotes={() => handleSaveAsNote(msg)}
                        isSavingNote={isSavingNoteId === msg.id}
                        isSavedNote={savedNoteId === msg.id}
                      />

                      <span
                        data-testid="message-model-badge"
                        className="hidden"
                      >
                        {msg.answer_path === 'gemini' ? (msg.model || activeModel || 'Gemini') : 'Deterministic mode'}
                      </span>
                    </div>
                  )}
                </div>
              ))}

              {isLoading && (
                <div className="flex items-center gap-3 p-4 bg-paper-surface rounded-2xl border border-border-hairline text-xs sm:text-sm text-ink-secondary max-w-sm shadow-subtle animate-pulse font-sans">
                  <Loader2 className="w-4 h-4 text-reading-primary animate-spin shrink-0" />
                  <span>Retrieving hybrid passages &amp; verifying citations...</span>
                </div>
              )}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* ======================================================== */}
        {/* COMPOSER & PERSISTENT SCOPE SECTION: Prominent, Docked */}
        {/* ======================================================== */}
        <div className="p-3.5 sm:p-5 bg-paper-surface/90 backdrop-blur-md border-t border-border-hairline shrink-0">
          <div className="max-w-3xl lg:max-w-4xl mx-auto w-full space-y-2.5">
            {/* Scope Guard Inline Prompt (When question refers to 'this paper' but >1 source selected) */}
            {!scopeGuardDismissed && (
              <ScopeGuardPrompt
                question={inputQuestion}
                selectedDocuments={selectedDocuments}
                onSelectSingleDoc={handleSelectSingleDoc}
                onContinueAll={() => setScopeGuardDismissed(true)}
              />
            )}

            {/* Persistent Scope Summary Bar */}
            <div className="flex items-center justify-between text-xs font-mono text-ink-muted px-1.5">
              <div className="flex items-center gap-2 truncate">
                <span className="text-ink font-semibold">
                  Scope: {selectedDocIds.length} of {documents.length} papers
                </span>
                <div className="hidden sm:flex items-center gap-1">
                  {selectedDocuments.slice(0, 5).map((doc, idx) => {
                    const ink = getPaperInk(doc.filename, idx);
                    const initial = getPaperInitial(doc.filename);
                    return (
                      <span
                        key={doc.id}
                        className="w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold text-white shrink-0"
                        style={{ backgroundColor: ink.hex }}
                        title={doc.filename}
                      >
                        {initial}
                      </span>
                    );
                  })}
                  {selectedDocuments.length > 5 && (
                    <span className="text-[10px] text-ink-muted">+{selectedDocuments.length - 5} more</span>
                  )}
                </div>
              </div>

              <button
                type="button"
                onClick={() => {
                  if (window.innerWidth >= 1024) {
                    setIsSourcesCollapsed(false);
                  } else {
                    setIsSourcesDrawerOpen(true);
                  }
                }}
                className="text-reading-primary hover:underline text-xs font-medium"
              >
                Change scope
              </button>
            </div>

            {/* Query Input Card: Claude-style rounded box */}
            <form onSubmit={handleAsk} className="relative flex items-center bg-paper-bg border border-border-hairline rounded-2xl shadow-sm p-1.5 focus-within:ring-2 focus-within:ring-reading-primary/20 focus-within:border-reading-primary transition-all">
              <input
                type="text"
                value={inputQuestion}
                onChange={(e) => {
                  setInputQuestion(e.target.value);
                  setScopeGuardDismissed(false);
                }}
                placeholder="Ask a technical or research question..."
                className="flex-1 min-w-0 px-4 py-2.5 text-sm sm:text-base bg-transparent text-ink placeholder:text-ink-muted focus:outline-none font-sans"
              />
              <button
                type="submit"
                disabled={!inputQuestion.trim() || isLoading}
                className="px-4 sm:px-5 py-2.5 bg-reading-primary hover:bg-reading-primary-hover disabled:opacity-40 text-white rounded-xl shadow-xs flex items-center gap-2 text-xs sm:text-sm font-medium transition-all shrink-0 select-none focus:outline-none focus:ring-2 focus:ring-reading-primary"
              >
                <span>Verify</span>
                <Send className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* ======================================================== */}
      {/* 3. RIGHT PANE: Citation Evidence Inspector (Desktop >= 1200px) */}
      {/* ======================================================== */}
      {/* CLOSED BY DEFAULT: Takes zero space when closed; returns space to chat */}
      <div
        id="desktop-citation-panel"
        aria-label="Citation Evidence Inspector Panel"
        className={`${
          isEvidenceInspectorOpen ? 'hidden lg:flex lg:w-96 xl:w-[440px]' : 'hidden'
        } shrink-0 bg-paper-surface border-l border-border-hairline flex-col h-full min-w-0 shadow-paper transition-all duration-300 z-10`}
      >
        <EvidenceInspector
          activeCitation={activeCitation}
          allCitations={activeAnswerCitations}
          onSelectCitation={(cite) => setActiveCitation(cite)}
          onClearCitation={() => {
            setActiveCitation(null);
            handleCloseDesktopEvidenceInspector();
          }}
          onCloseDrawer={handleCloseDesktopEvidenceInspector}
          onOpenDocument={openFullDocument}
        />
      </div>

      {/* ======================================================== */}
      {/* Scope Sources Slide-Over Drawer (< 1200px) */}
      {/* ======================================================== */}
      {isSourcesDrawerOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div
            className="fixed inset-0 bg-black/40 backdrop-blur-xs transition-opacity"
            onClick={handleCloseSourcesDrawer}
            aria-hidden="true"
          />
          <aside
            id="sources-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Scope Sources Drawer"
            className="relative w-80 max-w-[90vw] bg-paper-surface border-r border-border-hairline flex flex-col h-full z-10 shadow-paper-elevated"
          >
            <SourcesPanel
              documents={documents}
              selectedDocIds={selectedDocIds}
              onToggleDoc={handleToggleDoc}
              onSelectAll={handleSelectAll}
              onDeselectDoc={handleDeselectDoc}
              onCloseDrawer={handleCloseSourcesDrawer}
              isDrawer={true}
            />
          </aside>
        </div>
      )}

      {/* ======================================================== */}
      {/* Citation Evidence Inspector Slide-Over Drawer (< 1200px) */}
      {/* ======================================================== */}
      {isCitationDrawerOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex justify-end">
          <div
            className="fixed inset-0 bg-black/40 backdrop-blur-xs transition-opacity"
            onClick={handleCloseCitationDrawer}
            aria-hidden="true"
          />
          <aside
            id="citation-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Citation Evidence Inspector Drawer"
            className="relative w-96 max-w-[90vw] bg-paper-surface border-l border-border-hairline flex-col h-full z-10 shadow-paper-elevated flex"
          >
            <EvidenceInspector
              activeCitation={activeCitation}
              allCitations={activeAnswerCitations}
              onSelectCitation={(cite) => setActiveCitation(cite)}
              onClearCitation={() => {
                setActiveCitation(null);
                handleCloseCitationDrawer();
              }}
              onCloseDrawer={handleCloseCitationDrawer}
              onOpenDocument={openFullDocument}
              isDrawer={true}
            />
          </aside>
        </div>
      )}

      {/* Full Document Inspector Modal */}
      <DocumentDetailModal
        document={inspectDoc}
        initialPage={inspectDocInitialPage}
        onClose={() => setInspectDoc(null)}
      />
    </div>
  );
};
