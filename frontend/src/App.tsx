import React, { useState, useRef, useEffect } from 'react';
import { Menu, Upload, ShieldAlert } from 'lucide-react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { Sidebar, NavigationTab } from './components/layout/Sidebar';
import { DashboardView } from './features/dashboard/DashboardView';
import { DocumentLibrary } from './features/documents/DocumentLibrary';
import { ResearchWorkspace } from './features/research/ResearchWorkspace';
import { PaperComparisonView } from './features/compare/PaperComparisonView';
import { NotesView } from './features/notes/NotesView';
import { SettingsView } from './features/settings/SettingsView';
import { UsageIntelligenceView } from './features/usage/UsageIntelligenceView';
import { DesignPreview } from './features/preview/DesignPreview';
import { AdminDashboardView } from './features/admin/AdminDashboardView';
import { AdminSystemDiagnosticsView } from './features/admin/AdminSystemDiagnosticsView';
import { UploadModal } from './features/documents/UploadModal';
import { OrionLogo } from './components/icons/OrionLogo';
import { ThemeToggle } from './components/ui/ThemeToggle';
import { AuthHero } from './features/auth/AuthHero';
import { AccessPendingView } from './features/auth/AccessPendingView';
import { PublicDemoWorkspace } from './features/demo/PublicDemoWorkspace';
import { Toaster } from 'sonner';

const OrionAppContent: React.FC = () => {
  const { isAuthenticated, isLoading, user } = useAuth();
  const [isDemoMode, setIsDemoMode] = useState<boolean>(() => {
    if (typeof window !== 'undefined') {
      const p = window.location.pathname;
      const h = window.location.hash;
      return p === '/demo' || h === '#demo';
    }
    return false;
  });
  const [currentTab, setCurrentTab] = useState<NavigationTab>(() => {
    if (typeof window !== 'undefined') {
      const p = window.location.pathname;
      const h = window.location.hash;
      if (p === '/admin/diagnostics' || p === '/diagnostics' || h === '#diagnostics') return 'diagnostics';
      if (p === '/admin' || h === '#admin') return 'admin';
      if (p === '/compare' || h === '#compare') return 'compare';
      if (p === '/documents' || h === '#documents') return 'documents';
      if (p === '/notes' || h === '#notes') return 'notes';
      if (p === '/usage' || h === '#usage') return 'usage';
      if (p === '/settings' || h === '#settings') return 'settings';
      if (p === '/dashboard' || h === '#dashboard') return 'dashboard';
      if (p === '/design-preview' || h === '#preview') return 'preview';
      if (p === '/research' || h === '#research') return 'research';
    }
    return 'dashboard';
  });
  const [isGlobalUploadOpen, setIsGlobalUploadOpen] = useState<boolean>(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState<boolean>(false);
  const [refreshKey, setRefreshKey] = useState<number>(0);
  const sidebarToggleRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const handlePopState = () => {
      const p = window.location.pathname;
      const h = window.location.hash;
      setIsDemoMode(p === '/demo' || h === '#demo');
      if (p === '/admin/diagnostics' || p === '/diagnostics' || h === '#diagnostics') setCurrentTab('diagnostics');
      else if (p === '/admin' || h === '#admin') setCurrentTab('admin');
      else if (p === '/compare' || h === '#compare') setCurrentTab('compare');
      else if (p === '/documents' || h === '#documents') setCurrentTab('documents');
      else if (p === '/notes' || h === '#notes') setCurrentTab('notes');
      else if (p === '/usage' || h === '#usage') setCurrentTab('usage');
      else if (p === '/settings' || h === '#settings') setCurrentTab('settings');
      else if (p === '/dashboard' || h === '#dashboard') setCurrentTab('dashboard');
      else if (p === '/design-preview' || h === '#preview') setCurrentTab('preview');
      else setCurrentTab('research');
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const handleCloseSidebar = () => {
    setIsMobileSidebarOpen(false);
    sidebarToggleRef.current?.focus();
  };

  if (isLoading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-[#17130f] text-[#ffb84c]">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#ffb84c] border-t-transparent" />
          <span className="font-mono text-xs tracking-widest text-[#fff8eb]/60 uppercase">
            Initializing ORION...
          </span>
        </div>
      </div>
    );
  }

  // Active public demo mode takes precedence or is immediately accessible without login
  if (isDemoMode) {
    return (
      <PublicDemoWorkspace
        onExitDemo={() => {
          setIsDemoMode(false);
          if (typeof window !== 'undefined' && window.location.hash === '#demo') {
            window.history.pushState(null, '', window.location.pathname);
          }
        }}
        onOpenLogin={() => {
          setIsDemoMode(false);
          if (typeof window !== 'undefined' && window.location.hash === '#demo') {
            window.history.pushState(null, '', window.location.pathname);
          }
        }}
      />
    );
  }

  if (!isAuthenticated) {
    return (
      <AuthHero
        onEnterDemo={() => {
          setIsDemoMode(true);
          if (typeof window !== 'undefined') {
            window.location.hash = '#demo';
          }
        }}
      />
    );
  }

  // Redirect unapproved researchers to the dedicated Access Pending view
  if (user?.role !== 'admin' && user?.access_status && user?.access_status !== 'active') {
    return <AccessPendingView />;
  }

  return (
    <div className="flex flex-col md:flex-row h-screen w-screen overflow-hidden bg-paper-bg text-ink font-sans selection:bg-reading-primary/20 selection:text-ink">
      {/* Sidebar: Docked on >= 900px, Drawer on < 900px */}
      <Sidebar
        currentTab={currentTab}
        onSelectTab={(tab) => {
          setCurrentTab(tab);
          setIsMobileSidebarOpen(false);
        }}
        onOpenUpload={() => setIsGlobalUploadOpen(true)}
        isOpen={isMobileSidebarOpen}
        onClose={handleCloseSidebar}
      />

      {/* Main Feature View Container */}
      <div className="flex-1 min-w-0 min-h-0 flex flex-col h-full overflow-hidden">
        {/* Responsive Mobile / Narrow Top Bar (< 900px) */}
        <header className="md:hidden flex items-center justify-between px-3 sm:px-4 py-2.5 bg-paper-surface border-b border-border-hairline shrink-0 z-10">
          <div className="flex items-center gap-2.5">
            <button
              ref={sidebarToggleRef}
              type="button"
              onClick={() => setIsMobileSidebarOpen(true)}
              aria-label="Open navigation menu"
              aria-expanded={isMobileSidebarOpen}
              aria-controls="mobile-sidebar"
              className="p-1.5 rounded-lg text-ink-700 hover:text-ink-950 hover:bg-parchment-100 focus:outline-hidden focus:ring-2 focus:ring-navy-600 transition-colors"
            >
              <Menu className="w-5 h-5" />
            </button>
            <OrionLogo size={24} showWordmark={true} />
          </div>

          <div className="flex items-center gap-2">
            <ThemeToggle />
            <button
              type="button"
              onClick={() => setIsGlobalUploadOpen(true)}
              aria-label="Upload Research PDF"
              className="flex items-center gap-1.5 px-3 py-1.5 bg-navy-800 hover:bg-navy-900 text-white rounded-lg text-xs font-medium transition-all shadow-subtle"
            >
              <Upload className="w-3.5 h-3.5" />
              <span className="hidden xs:inline">Upload PDF</span>
            </button>
          </div>
        </header>

        {/* Feature Workspace */}
        <main className="flex-1 min-w-0 min-h-0 h-full overflow-hidden flex flex-col">
          {currentTab === 'dashboard' && (
            <div className="flex-1 overflow-y-auto">
              <DashboardView
                onNavigate={setCurrentTab}
                onOpenUpload={() => setIsGlobalUploadOpen(true)}
                refreshTrigger={refreshKey}
              />
            </div>
          )}
          {currentTab === 'documents' && (
            <div className="flex-1 overflow-y-auto">
              <DocumentLibrary />
            </div>
          )}
          {currentTab === 'research' && <ResearchWorkspace />}
          {currentTab === 'compare' && (
            <div className="flex-1 overflow-y-auto">
              <PaperComparisonView />
            </div>
          )}
          {currentTab === 'notes' && <NotesView />}
          {currentTab === 'usage' && (
            <div className="flex-1 overflow-y-auto">
              <UsageIntelligenceView />
            </div>
          )}
          {currentTab === 'settings' && (
            <div className="flex-1 overflow-y-auto">
              <SettingsView />
            </div>
          )}
          {currentTab === 'diagnostics' && (
            user?.role === 'admin' ? (
              <div className="flex-1 overflow-y-auto p-4 sm:p-6 md:p-8 max-w-7xl mx-auto w-full">
                <AdminSystemDiagnosticsView />
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-surface-primary text-text-primary">
                <div className="p-3 rounded-full bg-rose-500/10 text-rose-600 mb-3 border border-rose-500/20">
                  <ShieldAlert className="w-8 h-8" />
                </div>
                <h2 className="text-xl font-serif font-bold">Access Restricted</h2>
                <p className="text-xs text-text-secondary mt-1 max-w-sm">
                  Administrative privileges are required to access System Diagnostics. Your account does not have administrative oversight authorization.
                </p>
                <button
                  onClick={() => setCurrentTab('dashboard')}
                  className="mt-4 px-4 py-2 rounded-lg bg-navy-800 text-white text-xs font-medium hover:bg-navy-900 transition-colors"
                >
                  Return to Dashboard
                </button>
              </div>
            )
          )}
          {currentTab === 'preview' && (
            user?.role === 'admin' ? (
              <DesignPreview />
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-surface-primary text-text-primary">
                <div className="p-3 rounded-full bg-rose-500/10 text-rose-600 mb-3 border border-rose-500/20">
                  <ShieldAlert className="w-8 h-8" />
                </div>
                <h2 className="text-xl font-serif font-bold">Access Restricted</h2>
                <p className="text-xs text-text-secondary mt-1 max-w-sm">
                  Administrative privileges are required to access Design Tokens & UI. Your account does not have administrative oversight authorization.
                </p>
                <button
                  onClick={() => setCurrentTab('dashboard')}
                  className="mt-4 px-4 py-2 rounded-lg bg-navy-800 text-white text-xs font-medium hover:bg-navy-900 transition-colors"
                >
                  Return to Dashboard
                </button>
              </div>
            )
          )}
          {currentTab === 'admin' && (
            user?.role === 'admin' ? (
              <div className="flex-1 overflow-y-auto">
                <AdminDashboardView />
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-surface-primary text-text-primary">
                <div className="p-3 rounded-full bg-rose-500/10 text-rose-600 mb-3 border border-rose-500/20">
                  <ShieldAlert className="w-8 h-8" />
                </div>
                <h2 className="text-xl font-serif font-bold">Access Restricted</h2>
                <p className="text-xs text-text-secondary mt-1 max-w-sm">
                  Administrative privileges are required to access this console. Your account does not have administrative oversight authorization.
                </p>
                <button
                  onClick={() => setCurrentTab('dashboard')}
                  className="mt-4 px-4 py-2 rounded-lg bg-navy-800 text-white text-xs font-medium hover:bg-navy-900 transition-colors"
                >
                  Return to Dashboard
                </button>
              </div>
            )
          )}
        </main>
      </div>

      {/* Global Upload Modal */}
      <UploadModal
        isOpen={isGlobalUploadOpen}
        onClose={() => setIsGlobalUploadOpen(false)}
        onUploadSuccess={() => {
          setRefreshKey((k) => k + 1);
        }}
      />
    </div>
  );
};

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <OrionAppContent />
        <Toaster position="bottom-right" richColors />
      </AuthProvider>
    </ThemeProvider>
  );
}
