import React, { useEffect, useRef } from 'react';
import {
  LayoutDashboard,
  Files,
  Compass,
  GitCompare,
  BookMarked,
  Settings,
  Upload,
  X,
  Palette,
  Activity,
  LogOut,
  ShieldAlert,
} from 'lucide-react';
import { OrionLogo } from '../icons/OrionLogo';
import { useAuth } from '../../context/AuthContext';
import { ThemeToggle } from '../ui/ThemeToggle';

export type NavigationTab =
  | 'dashboard'
  | 'documents'
  | 'research'
  | 'compare'
  | 'notes'
  | 'usage'
  | 'settings'
  | 'preview'
  | 'admin'
  | 'diagnostics';

export interface SidebarProps {
  currentTab: NavigationTab;
  onSelectTab: (tab: NavigationTab) => void;
  onOpenUpload: () => void;
  documentCount?: number;
  isOpen?: boolean;
  onClose?: () => void;
}

const getUserInitials = (user: { display_name?: string | null; email?: string | null } | null): string => {
  if (!user) return 'R';
  if (user.display_name && user.display_name.trim()) {
    const cleanParts = user.display_name
      .trim()
      .split(/\s+/)
      .filter((p) => !/^(dr\.?|prof\.?|mr\.?|ms\.?|mrs\.?)$/i.test(p));
    const parts = cleanParts.length > 0 ? cleanParts : user.display_name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return parts[0].slice(0, 2).toUpperCase();
  }
  if (user.email && user.email.trim()) {
    const namePart = user.email.trim().split('@')[0];
    return namePart.slice(0, 2).toUpperCase();
  }
  return 'R';
};

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  onOpenUpload,
  documentCount = 0,
  isOpen = false,
  onClose,
}) => {
  const { user, signOut } = useAuth();
  const drawerRef = useRef<HTMLDivElement>(null);

  const displayName = user?.display_name?.trim() || user?.email || 'Researcher';
  const secondaryText = user?.display_name?.trim()
    ? (user?.institution ? `${user.institution} • ${user.email}` : user.email)
    : (user?.institution || undefined);
  const initials = getUserInitials(user);

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose?.();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const navItems = [
    { id: 'dashboard' as NavigationTab, label: 'Dashboard', icon: LayoutDashboard },
    { id: 'documents' as NavigationTab, label: 'Document Library', icon: Files, badge: documentCount },
    { id: 'research' as NavigationTab, label: 'Research Workspace', icon: Compass },
    { id: 'compare' as NavigationTab, label: 'Paper Comparison', icon: GitCompare },
    { id: 'notes' as NavigationTab, label: 'Research Notes', icon: BookMarked },
    { id: 'usage' as NavigationTab, label: 'Usage Intelligence', icon: Activity },
    { id: 'settings' as NavigationTab, label: 'Settings', icon: Settings },
    ...(user?.role === 'admin'
      ? [
          { id: 'admin' as NavigationTab, label: 'Admin Console', icon: ShieldAlert },
          { id: 'preview' as NavigationTab, label: 'Design Tokens & UI', icon: Palette },
        ]
      : []),
  ];

  const handleNavClick = (id: NavigationTab) => {
    onSelectTab(id);
    onClose?.();
  };

  const handleUploadClick = () => {
    onOpenUpload();
    onClose?.();
  };

  const renderContent = (isMobileDrawer: boolean) => (
    <>
      {/* Brand Header */}
      <div>
        <div className="p-4 sm:p-5 border-b border-parchment-200 flex items-center justify-between">
          <div>
            <OrionLogo size={28} />
            <p className="text-[11px] text-ink-500 font-serif italic mt-1.5">
              "Research deeper. Verify every answer."
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            <ThemeToggle />
            {isMobileDrawer && (
              <button
                type="button"
                onClick={onClose}
                aria-label="Close navigation sidebar"
                className="p-1.5 rounded-lg text-ink-500 hover:text-ink-900 hover:bg-parchment-200 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>
        </div>

        {/* Action Button */}
        <div className="p-3 sm:p-4">
          <button
            type="button"
            onClick={handleUploadClick}
            className="w-full flex items-center justify-center gap-2 bg-reading-primary hover:bg-reading-primary-hover text-reading-primary-fg font-medium py-2.5 px-3 sm:px-4 rounded-xl shadow-sm transition-all duration-150 text-xs sm:text-sm select-none"
          >
            <Upload className="w-4 h-4 shrink-0" />
            <span className="truncate">Upload Research PDF</span>
          </button>
        </div>

        {/* Navigation Items */}
        <nav className="px-2 sm:px-3 space-y-1" aria-label="Sidebar navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => handleNavClick(item.id)}
                aria-current={isActive ? 'page' : undefined}
                className={`w-full flex items-center justify-between px-3 py-2 sm:py-2.5 rounded-md text-xs sm:text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-reading-primary/10 text-reading-primary border border-reading-primary/20 shadow-xs font-semibold'
                    : 'text-ink-secondary hover:bg-paper-raised hover:text-ink'
                }`}
              >
                <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
                  <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-reading-primary' : 'text-ink-muted'}`} />
                  <span className="truncate">{item.label}</span>
                </div>
                {item.badge !== undefined && item.badge > 0 && (
                  <span className="text-[10px] sm:text-xs font-mono bg-paper-raised px-2 py-0.5 rounded-full text-ink-secondary shrink-0">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Account Profile Footer */}
      <div className="p-3 sm:p-4 border-t border-border-hairline bg-paper-surface shrink-0">
        <div className="flex items-center gap-2.5 sm:gap-3">
          <div
            className="w-8 h-8 sm:w-9 sm:h-9 rounded-full bg-reading-primary/10 border border-reading-primary/25 flex items-center justify-center text-reading-primary font-serif font-bold text-xs sm:text-sm shrink-0 select-none shadow-xs"
            aria-label={`Avatar for ${displayName}`}
          >
            {initials}
          </div>
          <div className="flex flex-col min-w-0 flex-1">
            <span
              className="text-xs sm:text-sm font-medium text-ink truncate leading-tight"
              title={displayName}
            >
              {displayName}
            </span>
            {secondaryText && (
              <span
                className="text-[10px] sm:text-[11px] text-ink-muted truncate leading-tight mt-0.5"
                title={secondaryText}
              >
                {secondaryText}
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={() => signOut()}
            title="Sign out of ORION"
            aria-label="Sign out"
            className="p-1.5 sm:p-2 rounded-lg text-ink-muted hover:text-ink hover:bg-paper-raised border border-transparent hover:border-border-hairline transition-all shrink-0 cursor-pointer"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </>
  );

  return (
    <>
      {/* Desktop Permanent Docked Sidebar (Visible on md: >= 900px) */}
      <aside
        id="desktop-sidebar"
        aria-label="Desktop Main Navigation"
        className="hidden md:flex md:w-56 lg:w-64 bg-paper-surface border-r border-border-hairline flex-col justify-between shrink-0 h-screen sticky top-0 z-20"
      >
        {renderContent(false)}
      </aside>

      {/* Mobile & Narrow Desktop Drawer Overlay (< md: < 900px) */}
      {isOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/40 backdrop-blur-xs transition-opacity"
            onClick={onClose}
            aria-hidden="true"
          />

          {/* Drawer Panel */}
          <aside
            ref={drawerRef}
            id="mobile-sidebar"
            role="dialog"
            aria-modal="true"
            aria-label="Navigation sidebar"
            className="relative w-72 max-w-[85vw] bg-paper-surface border-r border-border-hairline flex flex-col justify-between h-full z-10 shadow-paper-elevated"
          >
            {renderContent(true)}
          </aside>
        </div>
      )}
    </>
  );
};
