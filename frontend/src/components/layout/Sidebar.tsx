import React from 'react';
import {
  LayoutDashboard,
  Files,
  Compass,
  GitCompare,
  BookMarked,
  Settings,
  Upload,
  UserCheck,
  ShieldAlert,
} from 'lucide-react';
import { OrionLogo } from '../icons/OrionLogo';
import { useAuth } from '../../context/AuthContext';

export type NavigationTab = 'dashboard' | 'documents' | 'research' | 'compare' | 'notes' | 'settings';

interface SidebarProps {
  currentTab: NavigationTab;
  onSelectTab: (tab: NavigationTab) => void;
  onOpenUpload: () => void;
  documentCount?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  onOpenUpload,
  documentCount = 0,
}) => {
  const { user, switchUser } = useAuth();

  const navItems = [
    { id: 'dashboard' as NavigationTab, label: 'Dashboard', icon: LayoutDashboard },
    { id: 'documents' as NavigationTab, label: 'Document Library', icon: Files, badge: documentCount },
    { id: 'research' as NavigationTab, label: 'Research Workspace', icon: Compass },
    { id: 'compare' as NavigationTab, label: 'Paper Comparison', icon: GitCompare },
    { id: 'notes' as NavigationTab, label: 'Research Notes', icon: BookMarked },
    { id: 'settings' as NavigationTab, label: 'Settings & Metrics', icon: Settings },
  ];

  return (
    <aside className="w-64 bg-parchment-100 border-r border-parchment-300 flex flex-col justify-between shrink-0 h-screen sticky top-0">
      {/* Brand Header */}
      <div>
        <div className="p-5 border-b border-parchment-200">
          <OrionLogo size={32} />
          <p className="text-xs text-ink-500 font-serif italic mt-2">
            "Research deeper. Verify every answer."
          </p>
        </div>

        {/* Action Button */}
        <div className="p-4">
          <button
            type="button"
            onClick={onOpenUpload}
            className="w-full flex items-center justify-center gap-2 bg-navy-800 hover:bg-navy-900 text-white font-medium py-2 px-4 rounded-lg shadow-subtle transition-all duration-150 text-sm"
          >
            <Upload className="w-4 h-4" />
            <span>Upload Research PDF</span>
          </button>
        </div>

        {/* Navigation Items */}
        <nav className="px-3 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelectTab(item.id)}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-parchment-300 text-navy-950 shadow-xs font-semibold'
                    : 'text-ink-700 hover:bg-parchment-200 hover:text-ink-950'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 ${isActive ? 'text-navy-800' : 'text-ink-500'}`} />
                  <span>{item.label}</span>
                </div>
                {item.badge !== undefined && item.badge > 0 && (
                  <span className="text-xs font-mono bg-parchment-300 px-2 py-0.5 rounded-full text-ink-700">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* User & Tenant Session Footer */}
      <div className="p-4 border-t border-parchment-200 bg-parchment-50">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-forest-500 animate-pulse" />
            <span className="text-[11px] font-mono uppercase text-ink-500">Local Verified Mode</span>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-navy-100 border border-navy-200 flex items-center justify-center text-navy-800 font-serif font-bold text-xs">
            {user?.email[0].toUpperCase() || 'R'}
          </div>
          <div className="flex flex-col min-w-0 flex-1">
            <span className="text-xs font-medium text-ink-900 truncate">
              {user?.email || 'researcher'}
            </span>
            <span className="text-[10px] font-mono text-ink-500 truncate">
              ID: {user?.id}
            </span>
          </div>
        </div>

        {/* Tenant Switching for Testing Isolation */}
        <div className="mt-3 pt-2 border-t border-parchment-200 flex items-center justify-between text-xs">
          <span className="text-[10px] text-ink-500 font-mono">Test Tenant:</span>
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => switchUser('user_dev_researcher_001')}
              className={`px-1.5 py-0.5 rounded font-mono text-[10px] ${
                user?.id === 'user_dev_researcher_001'
                  ? 'bg-navy-800 text-white font-bold'
                  : 'bg-parchment-200 text-ink-700 hover:bg-parchment-300'
              }`}
            >
              User A
            </button>
            <button
              type="button"
              onClick={() => switchUser('user_dev_researcher_002')}
              className={`px-1.5 py-0.5 rounded font-mono text-[10px] ${
                user?.id === 'user_dev_researcher_002'
                  ? 'bg-navy-800 text-white font-bold'
                  : 'bg-parchment-200 text-ink-700 hover:bg-parchment-300'
              }`}
            >
              User B
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
};
