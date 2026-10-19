import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Sidebar, NavigationTab } from './components/layout/Sidebar';
import { DashboardView } from './features/dashboard/DashboardView';
import { DocumentLibrary } from './features/documents/DocumentLibrary';
import { ResearchWorkspace } from './features/research/ResearchWorkspace';
import { PaperComparisonView } from './features/compare/PaperComparisonView';
import { NotesView } from './features/notes/NotesView';
import { SettingsView } from './features/settings/SettingsView';
import { UploadModal } from './features/documents/UploadModal';

const OrionAppContent: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<NavigationTab>('dashboard');
  const [isGlobalUploadOpen, setIsGlobalUploadOpen] = useState<boolean>(false);

  return (
    <div className="flex min-h-screen bg-parchment-50 text-ink-900 font-sans selection:bg-navy-100 selection:text-navy-900">
      {/* Permanent Sidebar */}
      <Sidebar
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        onOpenUpload={() => setIsGlobalUploadOpen(true)}
      />

      {/* Main Feature View */}
      <main className="flex-1 min-w-0 overflow-y-auto">
        {currentTab === 'dashboard' && (
          <DashboardView
            onNavigate={setCurrentTab}
            onOpenUpload={() => setIsGlobalUploadOpen(true)}
          />
        )}
        {currentTab === 'documents' && <DocumentLibrary />}
        {currentTab === 'research' && <ResearchWorkspace />}
        {currentTab === 'compare' && <PaperComparisonView />}
        {currentTab === 'notes' && <NotesView />}
        {currentTab === 'settings' && <SettingsView />}
      </main>

      {/* Global Upload Modal */}
      <UploadModal
        isOpen={isGlobalUploadOpen}
        onClose={() => setIsGlobalUploadOpen(false)}
        onUploadSuccess={() => {
          // If on library, library refreshes itself
        }}
      />
    </div>
  );
};

export default function App() {
  return (
    <AuthProvider>
      <OrionAppContent />
    </AuthProvider>
  );
}
