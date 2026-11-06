import React, { useState, useEffect, useRef } from 'react';
import {
  BookOpen,
  Send,
  Loader2,
  Sparkles,
  ShieldCheck,
  AlertCircle,
  FileText,
  ExternalLink,
  ChevronRight,
  Filter,
  ArrowLeft,
  Lock,
  Zap,
  Info,
  Clock,
  Menu,
  X,
} from 'lucide-react';
import {
  DemoPaperItem,
  DemoExampleQuestion,
  DemoCitation,
  DemoAskResponse,
  DemoStatusResponse,
} from '../../types';
import { api } from '../../services/api';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Card } from '../../components/ui/Card';
import { ThemeToggle } from '../../components/ui/ThemeToggle';
import { OrionLogo } from '../../components/icons/OrionLogo';
import { DemoPdfViewer } from './DemoPdfViewer';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: DemoCitation[];
  groundingScore?: number;
  isCached?: boolean;
  insufficientEvidence?: boolean;
  latencyMs?: number;
}

interface PublicDemoWorkspaceProps {
  onExitDemo: () => void;
  onOpenLogin: () => void;
}

export const PublicDemoWorkspace: React.FC<PublicDemoWorkspaceProps> = ({
  onExitDemo,
  onOpenLogin,
}) => {
  // Demo metadata state
  const [status, setStatus] = useState<DemoStatusResponse | null>(null);
  const [papers, setPapers] = useState<DemoPaperItem[]>([]);
  const [examples, setExamples] = useState<DemoExampleQuestion[]>([]);
  const [isLoadingInitial, setIsLoadingInitial] = useState<boolean>(true);
  const [initialError, setInitialError] = useState<string | null>(null);

  // Chat & filter state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [queryInput, setQueryInput] = useState<string>('');
  const [selectedPaperIds, setSelectedPaperIds] = useState<string[]>([]);
  const [isAsking, setIsAsking] = useState<boolean>(false);
  const [askError, setAskError] = useState<string | null>(null);

  // Evidence viewer state
  const [inspectingPaper, setInspectingPaper] = useState<DemoPaperItem | null>(null);
  const [inspectingPage, setInspectingPage] = useState<number>(1);
  const [inspectingPassage, setInspectingPassage] = useState<string>('');

  // Mobile sidebar drawer state
  const [isMobilePanelOpen, setIsMobilePanelOpen] = useState<boolean>(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load initial demo status, papers, and example questions
  useEffect(() => {
    let isMounted = true;
    async function loadDemoData() {
      setIsLoadingInitial(true);
      setInitialError(null);
      try {
        const [statusRes, papersRes, examplesRes] = await Promise.all([
          api.getDemoStatus().catch(() => null),
          api.getDemoPapers().catch(() => []),
          api.getDemoExamples().catch(() => []),
        ]);

        if (!isMounted) return;

        if (statusRes && !statusRes.enabled) {
          setStatus(statusRes);
          setInitialError('Public Demo Mode is currently inactive.');
          setIsLoadingInitial(false);
          return;
        }

        setStatus(statusRes);
        setPapers(papersRes);
        setExamples(examplesRes);
      } catch (err: any) {
        if (isMounted) {
          setInitialError(err?.message || 'Could not connect to ORION Demo backend.');
        }
      } finally {
        if (isMounted) setIsLoadingInitial(false);
      }
    }

    loadDemoData();
    return () => {
      isMounted = false;
    };
  }, []);

  // Scroll to bottom on new messages
  useEffect(() => {
    if (typeof messagesEndRef.current?.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isAsking]);

  const handleSelectPaperFilter = (docId: string) => {
    setSelectedPaperIds((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    );
  };

  const handleOpenViewer = (paper: DemoPaperItem, page: number = 1, passage: string = '') => {
    setInspectingPaper(paper);
    setInspectingPage(page);
    setInspectingPassage(passage);
  };

  const handleAsk = async (questionText: string) => {
    const q = questionText.trim();
    if (!q || isAsking) return;

    if (q.length > 250) {
      setAskError('Demo queries are limited to 250 characters. Please shorten your question.');
      return;
    }

    setAskError(null);
    const userMsg: ChatMessage = {
      id: `msg_user_${Date.now()}`,
      role: 'user',
      content: q,
    };
    setMessages((prev) => [...prev, userMsg]);
    setQueryInput('');
    setIsAsking(true);

    try {
      const activeFilter = selectedPaperIds.length > 0 ? selectedPaperIds : undefined;
      const res: DemoAskResponse = await api.askDemoQuestion(q, activeFilter);

      const assistantMsg: ChatMessage = {
        id: `msg_asst_${Date.now()}`,
        role: 'assistant',
        content: res.answer,
        citations: res.citations,
        groundingScore: res.grounding_score,
        isCached: res.is_cached,
        insufficientEvidence: res.insufficient_evidence,
        latencyMs: res.latency_ms,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg =
        err?.message || 'Failed to process inquiry. Rate limit may have been reached.';
      setAskError(errorMsg);
    } finally {
      setIsAsking(false);
    }
  };

  const handleTriggerExample = (example: DemoExampleQuestion) => {
    setQueryInput(example.question);
    handleAsk(example.question);
    setIsMobilePanelOpen(false);
  };

  // If public demo feature flag is disabled
  if (!isLoadingInitial && status && !status.enabled) {
    return (
      <div className="flex h-screen w-screen flex-col items-center justify-center bg-paper-bg p-6 text-center text-ink font-sans">
        <div className="max-w-md space-y-4 rounded-xl border border-border-hairline bg-paper-surface p-8 shadow-lg">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-500/10 text-amber-600">
            <Lock className="h-6 w-6" />
          </div>
          <h2 className="font-serif text-2xl font-medium tracking-tight">Public Demo Offline</h2>
          <p className="text-sm text-ink-secondary">
            Public Demo mode is currently disabled by system administrators. Please sign in to access
            your private research workspace.
          </p>
          <div className="pt-2 flex flex-col gap-2">
            <Button variant="primary" onClick={onOpenLogin} className="w-full">
              Sign In to Private Workspace
            </Button>
            <Button variant="ghost" onClick={onExitDemo} className="w-full text-xs text-ink-muted">
              Return to Landing Page
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-paper-bg text-ink font-sans selection:bg-reading-primary/20">
      {/* Main Container */}
      <div className="flex flex-col flex-1 h-full min-w-0 overflow-hidden">
        {/* Top Header Bar */}
        <header className="flex items-center justify-between px-4 py-3 border-b border-border-hairline bg-paper-surface/90 backdrop-blur z-20 shrink-0">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setIsMobilePanelOpen(true)}
              className="lg:hidden p-1.5 rounded-md hover:bg-paper-bg text-ink-muted"
              aria-label="Open Papers & Examples Drawer"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-2 cursor-pointer" onClick={onExitDemo}>
              <OrionLogo size={22} />
              <span className="font-mono text-sm tracking-widest font-semibold text-ink uppercase">
                ORION
              </span>
            </div>
            <div className="h-4 w-px bg-border-hairline hidden sm:block" />
            <Badge variant="verified" className="hidden sm:inline-flex text-[11px] font-mono">
              PUBLIC DEMO MODE
            </Badge>
          </div>

          {/* Center Info / Capacity Tag */}
          <div className="hidden md:flex items-center gap-2 text-xs text-ink-muted font-mono">
            <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
              <ShieldCheck className="w-3.5 h-3.5" /> 4 Curated EPR Papers (CC BY 4.0)
            </span>
            <span>•</span>
            <span className="flex items-center gap-1">
              <Zap className="w-3.5 h-3.5 text-amber-500" /> Grounded Gemini Synthesis
            </span>
          </div>

          {/* Right Action Buttons */}
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Button
              variant="outline"
              size="sm"
              onClick={onOpenLogin}
              className="text-xs font-mono h-8 border-border-hairline text-ink hover:text-amber-600 dark:hover:text-[#ffb84c] hover:border-amber-500/40"
            >
              <Lock className="w-3.5 h-3.5 mr-1.5 text-ink-muted" />
              Sign In to Private
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={onExitDemo}
              className="text-xs font-mono h-8 text-ink-muted hover:text-ink hidden sm:inline-flex"
            >
              Exit Demo
            </Button>
          </div>
        </header>

        {/* Workspace Body: Split View (Catalog/Examples + Chat + Optional PDF Viewer) */}
        <div className="flex flex-1 min-h-0 overflow-hidden relative">
          {/* Left Panel: Curated Papers & Suggested Questions (Docked >= 1024px) */}
          <aside
            className={`
              fixed lg:static inset-y-0 left-0 z-30 w-80 sm:w-88 lg:w-80 xl:w-96
              bg-paper-surface border-r border-border-hairline flex flex-col h-full
              overflow-hidden shrink-0 transition-transform duration-200 ease-in-out
              ${isMobilePanelOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full lg:translate-x-0'}
            `}
            role="region"
            aria-label="Curated Papers and Questions"
          >
            {/* Mobile Close Button */}
            <div className="lg:hidden flex items-center justify-between p-3 border-b border-border-hairline bg-paper-bg/50">
              <span className="text-xs font-mono font-semibold text-ink uppercase tracking-wider">
                Corpus &amp; Questions
              </span>
              <button
                type="button"
                onClick={() => setIsMobilePanelOpen(false)}
                className="p-1 rounded text-ink-muted hover:text-ink"
                aria-label="Close Drawer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto overflow-x-hidden min-w-0 max-w-full p-3.5 sm:p-4 space-y-6">
              {/* 1. Curated Papers Section */}
              <div className="space-y-3 min-w-0 max-w-full">
                <div className="flex items-center justify-between gap-2 min-w-0">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <BookOpen className="w-4 h-4 text-amber-500 dark:text-[#ffb84c] shrink-0" />
                    <h3 className="text-xs font-mono font-semibold text-ink uppercase tracking-wider truncate">
                      Curated EPR Papers ({papers.length})
                    </h3>
                  </div>
                  {selectedPaperIds.length > 0 && (
                    <button
                      type="button"
                      onClick={() => setSelectedPaperIds([])}
                      className="text-[10px] font-mono text-amber-600 dark:text-[#ffb84c] hover:underline shrink-0"
                    >
                      Clear filter
                    </button>
                  )}
                </div>
                <p className="text-xs text-ink-muted leading-relaxed break-words">
                  Peer-reviewed literature published under Creative Commons CC BY 4.0. Click a paper to
                  filter Q&amp;A or inspect PDF.
                </p>

                <div className="space-y-2.5 w-full min-w-0 max-w-full">
                  {papers.map((p) => {
                    const isSelected = selectedPaperIds.includes(p.id);
                    return (
                      <div
                        key={p.id}
                        className={`w-full min-w-0 max-w-full p-3 sm:p-3.5 rounded-lg border text-left transition-all box-border ${
                          isSelected
                            ? 'border-amber-500/60 dark:border-[#ffb84c]/60 bg-amber-500/10 dark:bg-[#ffb84c]/10 shadow-sm'
                            : 'border-border-hairline hover:border-amber-500/30 dark:hover:border-[#ffb84c]/30 bg-paper-bg/40'
                        }`}
                      >
                        <button
                          type="button"
                          onClick={() => handleSelectPaperFilter(p.id)}
                          className="w-full min-w-0 text-left block focus:outline-none"
                        >
                          <h4 className="text-xs font-semibold text-ink font-serif leading-snug break-words hover:text-amber-600 dark:hover:text-[#ffb84c] transition-colors">
                            {p.title}
                          </h4>
                          <p className="text-[11px] text-ink-muted mt-1.5 leading-relaxed break-words">
                            {p.authors} ({p.year})
                          </p>
                        </button>
                        <div className="flex items-center justify-between mt-3 pt-2 border-t border-border-hairline/60 text-[10px] font-mono">
                          <div className="flex items-center gap-1.5 text-ink-muted min-w-0 flex-wrap">
                            <span>{p.total_pages} pages</span>
                            <span>•</span>
                            <span className="text-emerald-600 dark:text-emerald-400 font-semibold shrink-0">
                              CC BY 4.0
                            </span>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleOpenViewer(p, 1);
                            }}
                            className="h-6 px-2 text-[10px] font-mono text-amber-600 dark:text-[#ffb84c] hover:bg-amber-500/10 dark:hover:bg-[#ffb84c]/10 shrink-0 border border-amber-500/20"
                            title="Inspect authentic PDF binary"
                          >
                            <FileText className="w-3 h-3 mr-1" />
                            PDF
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* 2. Suggested Research Questions */}
              <div className="space-y-3 pt-2 border-t border-border-hairline min-w-0 max-w-full">
                <div className="flex items-center gap-1.5 min-w-0">
                  <Sparkles className="w-4 h-4 text-amber-500 dark:text-[#ffb84c] shrink-0" />
                  <h3 className="text-xs font-mono font-semibold text-ink uppercase tracking-wider truncate">
                    Suggested Inquiries ({examples.length})
                  </h3>
                </div>
                <p className="text-xs text-ink-muted leading-relaxed break-words">
                  Click any question for verified, evidence-grounded answers returning with 0 token
                  delay.
                </p>

                <div className="space-y-2 w-full min-w-0 max-w-full">
                  {examples.map((ex) => (
                    <button
                      key={ex.id}
                      type="button"
                      onClick={() => handleTriggerExample(ex)}
                      className="w-full min-w-0 max-w-full p-2.5 sm:p-3 rounded-lg border border-border-hairline bg-paper-bg/30 hover:border-amber-500/40 dark:hover:border-[#ffb84c]/40 hover:bg-amber-500/5 dark:hover:bg-[#ffb84c]/5 text-left transition-all group box-border"
                    >
                      <div className="flex items-center justify-between text-[10px] font-mono text-ink-muted mb-1 gap-2">
                        <span className="text-amber-600 dark:text-[#ffb84c] font-medium truncate">
                          {ex.category}
                        </span>
                        <ChevronRight className="w-3 h-3 text-ink-muted group-hover:translate-x-0.5 group-hover:text-amber-500 dark:group-hover:text-[#ffb84c] transition-all shrink-0" />
                      </div>
                      <p className="text-xs text-ink font-serif leading-snug break-words group-hover:text-amber-600 dark:group-hover:text-[#ffb84c] transition-colors">
                        "{ex.question}"
                      </p>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Sidebar Footer */}
            <div className="p-3 border-t border-border-hairline bg-paper-bg/40 text-[11px] font-mono text-ink-muted flex items-center justify-between">
              <span>Read-only sandbox</span>
              <span className="text-emerald-600 dark:text-emerald-400">Isolated</span>
            </div>
          </aside>

          {/* Backdrop for mobile drawer */}
          {isMobilePanelOpen && (
            <div
              className="fixed inset-0 bg-black/40 z-20 lg:hidden"
              onClick={() => setIsMobilePanelOpen(false)}
            />
          )}

          {/* Center Column: Research Chat */}
          <main
            className="flex-1 flex flex-col h-full min-w-0 bg-paper-bg overflow-hidden"
            role="main"
          >
            {/* Active Filter Strip if papers selected */}
            {selectedPaperIds.length > 0 && (
              <div className="flex items-center justify-between px-4 py-2 bg-amber-500/10 dark:bg-[#ffb84c]/10 border-b border-border-hairline text-xs font-mono">
                <div className="flex items-center gap-2 text-ink">
                  <Filter className="w-3.5 h-3.5 text-amber-500 dark:text-[#ffb84c]" />
                  <span>
                    Scoped to <strong>{selectedPaperIds.length}</strong> of {papers.length} demo papers
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedPaperIds([])}
                  className="text-amber-600 dark:text-[#ffb84c] hover:underline text-[11px]"
                >
                  Reset to All Papers
                </button>
              </div>
            )}

            {/* Message Stream */}
            <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
              {messages.length === 0 ? (
                // Welcome / Empty State
                <div className="max-w-2xl mx-auto my-auto py-8 sm:py-16 text-center space-y-6">
                  <div className="mx-auto w-12 h-12 rounded-xl bg-amber-500/10 dark:bg-[#ffb84c]/10 flex items-center justify-center text-amber-600 dark:text-[#ffb84c]">
                    <OrionLogo size={28} />
                  </div>
                  <div className="space-y-2">
                    <p className="text-xs uppercase tracking-widest font-mono text-amber-600 dark:text-[#ffb84c] font-semibold">
                      ORION Academic Research Assistant
                    </p>
                    <h2 className="text-2xl sm:text-3xl font-serif font-medium text-ink tracking-tight">
                      Explore Public Research Intelligence
                    </h2>
                    <p className="text-sm text-ink-secondary max-w-lg mx-auto leading-relaxed">
                      Evaluate ORION's multi-tier evidence grounding and dense retrieval across a curated
                      corpus of peer-reviewed <strong>Extended Producer Responsibility (EPR)</strong>{' '}
                      literature. Every claim is anchored to exact source pages.
                    </p>
                  </div>

                  {/* Quick Starter Cards */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-left pt-4 max-w-xl mx-auto">
                    {examples.slice(0, 4).map((ex) => (
                      <button
                        key={ex.id}
                        type="button"
                        onClick={() => handleTriggerExample(ex)}
                        className="p-3 rounded-lg border border-border-hairline bg-paper-surface hover:border-amber-500/50 dark:hover:border-[#ffb84c]/50 hover:shadow-sm transition-all text-left"
                      >
                        <span className="text-[10px] font-mono text-amber-600 dark:text-[#ffb84c] font-semibold block mb-1">
                          {ex.category}
                        </span>
                        <p className="text-xs font-serif text-ink line-clamp-2 leading-snug">
                          {ex.question}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                // Message List
                messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
                  >
                    {msg.role === 'user' ? (
                      // User Message Bubble
                      <div className="max-w-xl bg-reading-primary text-white rounded-2xl rounded-tr-sm px-4 py-3 shadow-sm text-sm sm:text-base font-sans">
                        {msg.content}
                      </div>
                    ) : (
                      // Assistant Grounded Answer Card
                      <Card className="max-w-3xl w-full p-4 sm:p-6 bg-paper-surface border-border-hairline shadow-sm space-y-4">
                        {/* Status Header */}
                        <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-border-hairline text-xs font-mono">
                          <div className="flex items-center gap-2">
                            <span className="flex items-center gap-1 font-semibold text-reading-primary">
                              <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                              ORION Evidence Synthesis
                            </span>
                            {msg.isCached && (
                              <Badge variant="verified" className="text-[10px] py-0.5">
                                ⚡ Verified Cache
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-3 text-ink-muted text-[11px]">
                            {msg.latencyMs !== undefined && (
                              <span className="flex items-center gap-1">
                                <Clock className="w-3 h-3" /> {msg.latencyMs}ms
                              </span>
                            )}
                            {msg.groundingScore !== undefined && msg.groundingScore > 0 && (
                              <span className="text-emerald-700 dark:text-emerald-400 font-semibold">
                                {Math.round(msg.groundingScore * 100)}% Grounded
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Answer Body */}
                        <div className="font-serif text-ink text-sm sm:text-base leading-relaxed whitespace-pre-wrap">
                          {msg.content}
                        </div>

                        {/* Abstention Banner if outside scope */}
                        {msg.insufficientEvidence && (
                          <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg text-xs text-amber-800 dark:text-amber-200 flex items-start gap-2">
                            <AlertCircle className="w-4 h-4 shrink-0 text-amber-600 mt-0.5" />
                            <div>
                              <strong className="block font-medium">Literature Boundary Notice</strong>
                              The public evaluation assistant abstains from hallucinating answers to
                              unsupported queries outside the 4 approved EPR benchmark papers.
                            </div>
                          </div>
                        )}

                        {/* Citations & Evidence Panel */}
                        {msg.citations && msg.citations.length > 0 && (
                          <div className="pt-3 border-t border-border-hairline space-y-2">
                            <h4 className="text-xs font-mono font-semibold uppercase tracking-wider text-ink-muted">
                              Evidence Grounding &amp; Page References ({msg.citations.length})
                            </h4>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                              {msg.citations.map((cite, cIdx) => {
                                const paperMeta = papers.find((p) => p.id === cite.document_id);
                                return (
                                  <div
                                    key={cIdx}
                                    className="p-3 rounded-lg border border-border-hairline bg-paper-bg/40 hover:border-reading-primary/40 transition-colors text-left space-y-1.5"
                                  >
                                    <div className="flex items-center justify-between text-xs">
                                      <span className="font-semibold text-ink font-serif truncate">
                                        [{cIdx + 1}] {cite.paper_title || cite.filename}
                                      </span>
                                      <span className="font-mono text-[10px] text-reading-primary shrink-0 ml-1">
                                        p. {cite.page_number}
                                      </span>
                                    </div>
                                    <p className="text-xs text-ink-secondary italic line-clamp-3 leading-snug">
                                      "{cite.exact_passage}"
                                    </p>
                                    <div className="pt-1 flex items-center justify-end">
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => {
                                          if (paperMeta) {
                                            handleOpenViewer(
                                              paperMeta,
                                              cite.page_number,
                                              cite.exact_passage
                                            );
                                          }
                                        }}
                                        className="h-6 px-2 text-[10px] font-mono text-reading-primary hover:bg-reading-primary/10"
                                      >
                                        Inspect Source Page &rarr;
                                      </Button>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </Card>
                    )}
                  </div>
                ))
              )}

              {/* In-Flight Thinking Indicator */}
              {isAsking && (
                <div className="flex items-center gap-2 text-xs font-mono text-ink-muted py-2">
                  <Loader2 className="w-4 h-4 animate-spin text-reading-primary" />
                  <span>Synthesizing evidence across curated literature...</span>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Error Banner */}
            {askError && (
              <div className="mx-4 mb-2 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-xs text-red-700 dark:text-red-300 flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  {askError}
                </span>
                <button
                  type="button"
                  onClick={() => setAskError(null)}
                  className="text-xs underline ml-2"
                >
                  Dismiss
                </button>
              </div>
            )}

            {/* Input Inquiry Bar */}
            <div className="p-4 border-t border-border-hairline bg-paper-surface">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleAsk(queryInput);
                }}
                className="max-w-3xl mx-auto space-y-2"
              >
                <div className="relative flex items-end rounded-xl border border-border-hairline bg-paper-bg focus-within:border-reading-primary focus-within:ring-1 focus-within:ring-reading-primary transition-all p-2">
                  <textarea
                    ref={inputRef}
                    rows={2}
                    value={queryInput}
                    maxLength={250}
                    onChange={(e) => setQueryInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleAsk(queryInput);
                      }
                    }}
                    placeholder="Ask a question on Extended Producer Responsibility (e.g. policy instruments, Somantri platform)..."
                    className="w-full resize-none bg-transparent px-2 text-sm text-ink placeholder:text-ink-muted focus:outline-none leading-relaxed font-sans"
                    disabled={isAsking}
                  />
                  <div className="flex items-center gap-2 shrink-0 pb-1 pr-1">
                    <span className="text-[10px] font-mono text-ink-muted">
                      {queryInput.length}/250
                    </span>
                    <Button
                      type="submit"
                      size="sm"
                      disabled={isAsking || !queryInput.trim()}
                      className="h-8 w-8 p-0 rounded-lg bg-reading-primary text-white hover:bg-reading-primary/90"
                      aria-label="Send Inquiry"
                    >
                      {isAsking ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Send className="w-4 h-4" />
                      )}
                    </Button>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] font-mono text-ink-muted px-1">
                  <span>Press Enter to send • Shift+Enter for new line</span>
                  <span>Rate limited to 5 req/min</span>
                </div>
              </form>
            </div>
          </main>

          {/* Right Panel / Modal Drawer: PDF Evidence Viewer */}
          {inspectingPaper && (
            <div className="w-full lg:w-[480px] xl:w-[560px] h-full shrink-0 z-40 fixed lg:static inset-y-0 right-0 shadow-2xl lg:shadow-none animate-in slide-in-from-right duration-200">
              <DemoPdfViewer
                paper={inspectingPaper}
                initialPage={inspectingPage}
                highlightPassage={inspectingPassage}
                onClose={() => setInspectingPaper(null)}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

