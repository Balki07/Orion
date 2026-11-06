import React, { useState, useEffect } from 'react';
import {
  UserCheck,
  Lock,
  HardDrive,
  Sliders,
  Activity,
  CheckCircle2,
  AlertCircle,
  Shield,
  ShieldCheck,
  Key,
  LogOut,
  Laptop,
  Smartphone,
  Cpu,
  Layers,
  FileText,
  Calendar,
  Save,
  RefreshCw,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { UserUsage, StorageUsageResponse, UserSessionItem, ResearchPreferences, SystemSettings } from '../../types';
import {
  getResearchPreferences,
  saveResearchPreferences,
  DEFAULT_RESEARCH_PREFERENCES,
} from '../../utils/researchPreferences';

export const SettingsView: React.FC = () => {
  const { user } = useAuth();
  const [activeSection, setActiveSection] = useState<'profile' | 'security' | 'storage' | 'preferences' | 'activity'>('profile');

  // Usage & Settings state
  const [usage, setUsage] = useState<UserUsage | null>(null);
  const [storageUsage, setStorageUsage] = useState<StorageUsageResponse | null>(null);
  const [systemSettings, setSystemSettings] = useState<SystemSettings | null>(null);
  const [sessions, setSessions] = useState<UserSessionItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // Profile Edit state
  const [displayName, setDisplayName] = useState<string>(user?.display_name || '');
  const [profileSaving, setProfileSaving] = useState<boolean>(false);
  const [profileMessage, setProfileMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Password Change state
  const [currentPassword, setCurrentPassword] = useState<string>('');
  const [newPassword, setNewPassword] = useState<string>('');
  const [confirmPassword, setConfirmPassword] = useState<string>('');
  const [passwordLoading, setPasswordLoading] = useState<boolean>(false);
  const [passwordMessage, setPasswordMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Session Revocation state
  const [revokingSessions, setRevokingSessions] = useState<boolean>(false);
  const [sessionMessage, setSessionMessage] = useState<string | null>(null);

  // Research Preferences state
  const [preferences, setPreferences] = useState<ResearchPreferences>(getResearchPreferences);
  const [prefsSavedMessage, setPrefsSavedMessage] = useState<string | null>(null);

  useEffect(() => {
    if (user?.display_name) {
      setDisplayName(user.display_name);
    }
  }, [user]);

  useEffect(() => {
    loadSettingsData();
  }, []);

  const loadSettingsData = async () => {
    setLoading(true);
    try {
      const [uData, sData, sysData, sessData] = await Promise.all([
        api.getUsage().catch(() => null),
        api.getStorageUsage().catch(() => null),
        api.getSettings().catch(() => null),
        api.listAuthSessions().catch(() => []),
      ]);
      setUsage(uData);
      setStorageUsage(sData);
      setSystemSettings(sysData);
      setSessions(sessData || []);
    } catch (err) {
      console.error('Failed to load settings data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!displayName.trim() || displayName.trim().length < 2) {
      setProfileMessage({ type: 'error', text: 'Display name must be at least 2 characters long.' });
      return;
    }
    setProfileSaving(true);
    setProfileMessage(null);
    try {
      await api.updateProfile({ display_name: displayName.trim() });
      setProfileMessage({ type: 'success', text: 'Profile display name updated successfully.' });
    } catch (err: any) {
      setProfileMessage({ type: 'error', text: err?.message || 'Failed to update profile.' });
    } finally {
      setProfileSaving(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordMessage(null);

    if (!currentPassword) {
      setPasswordMessage({ type: 'error', text: 'Please enter your current password.' });
      return;
    }
    if (newPassword.length < 8) {
      setPasswordMessage({ type: 'error', text: 'New password must be at least 8 characters long.' });
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordMessage({ type: 'error', text: 'New passwords do not match.' });
      return;
    }

    setPasswordLoading(true);
    try {
      await api.changePassword(currentPassword, newPassword);
      setPasswordMessage({ type: 'success', text: 'Password changed successfully.' });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      setPasswordMessage({ type: 'error', text: err?.message || 'Failed to change password.' });
    } finally {
      setPasswordLoading(false);
    }
  };

  const handleRevokeOtherSessions = async () => {
    setRevokingSessions(true);
    setSessionMessage(null);
    try {
      await api.revokeOtherSessions();
      setSessionMessage('All other active sessions have been revoked.');
      const updated = await api.listAuthSessions().catch(() => []);
      setSessions(updated);
    } catch (err: any) {
      setSessionMessage(err?.message || 'Failed to revoke sessions.');
    } finally {
      setRevokingSessions(false);
    }
  };

  const handleSavePreferences = (e: React.FormEvent) => {
    e.preventDefault();
    saveResearchPreferences(preferences);
    setPrefsSavedMessage('Research preferences saved and active in Research Workspace.');
    setTimeout(() => setPrefsSavedMessage(null), 4000);
  };

  const storageUsedMb = storageUsage
    ? (storageUsage.total_storage_mb ?? (storageUsage.used_storage_bytes ? storageUsage.used_storage_bytes / (1024 * 1024) : 0))
    : usage
    ? (usage.storage_mb_used ?? (usage.total_storage_bytes ? usage.total_storage_bytes / (1024 * 1024) : 0))
    : 0;
  const storageQuotaMb = storageUsage
    ? (storageUsage.storage_quota_mb ?? storageUsage.quota_mb ?? 500)
    : usage
    ? (usage.storage_quota_mb ?? 500)
    : 500;
  const remainingStorageMb = storageUsage
    ? (storageUsage.remaining_storage_mb ?? Math.max(0, storageQuotaMb - storageUsedMb))
    : Math.max(0, storageQuotaMb - storageUsedMb);
  const storagePercent = storageUsage
    ? (storageUsage.quota_usage_percent ?? storageUsage.usage_percentage ?? Math.min(Math.round((storageUsedMb / storageQuotaMb) * 100), 100))
    : Math.min(Math.round((storageUsedMb / storageQuotaMb) * 100), 100);

  return (
    <div className="p-4 sm:p-6 md:p-8 max-w-5xl mx-auto space-y-6 sm:space-y-8">
      {/* Header */}
      <div className="border-b border-parchment-300 pb-4 sm:pb-5">
        <h1 className="text-xl sm:text-2xl font-serif font-bold text-ink-950">
          Settings
        </h1>
        <p className="text-xs text-ink-500 mt-1">
          Manage your researcher profile, security credentials, 500 MB storage allocation, and scholarly preferences.
        </p>
      </div>

      {/* Navigation Pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 border-b border-parchment-200">
        <button
          type="button"
          onClick={() => setActiveSection('profile')}
          className={`px-3.5 py-2 rounded-lg text-xs font-medium flex items-center gap-2 whitespace-nowrap transition-colors ${
            activeSection === 'profile'
              ? 'bg-navy-800 text-white font-semibold shadow-xs'
              : 'text-ink-600 hover:text-ink-950 hover:bg-parchment-200/60'
          }`}
        >
          <UserCheck className="w-4 h-4" />
          <span>Account & Profile</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveSection('security')}
          className={`px-3.5 py-2 rounded-lg text-xs font-medium flex items-center gap-2 whitespace-nowrap transition-colors ${
            activeSection === 'security'
              ? 'bg-navy-800 text-white font-semibold shadow-xs'
              : 'text-ink-600 hover:text-ink-950 hover:bg-parchment-200/60'
          }`}
        >
          <Lock className="w-4 h-4" />
          <span>Security & Privacy</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveSection('storage')}
          className={`px-3.5 py-2 rounded-lg text-xs font-medium flex items-center gap-2 whitespace-nowrap transition-colors ${
            activeSection === 'storage'
              ? 'bg-navy-800 text-white font-semibold shadow-xs'
              : 'text-ink-600 hover:text-ink-950 hover:bg-parchment-200/60'
          }`}
        >
          <HardDrive className="w-4 h-4" />
          <span>Storage & Uploads</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveSection('preferences')}
          className={`px-3.5 py-2 rounded-lg text-xs font-medium flex items-center gap-2 whitespace-nowrap transition-colors ${
            activeSection === 'preferences'
              ? 'bg-navy-800 text-white font-semibold shadow-xs'
              : 'text-ink-600 hover:text-ink-950 hover:bg-parchment-200/60'
          }`}
        >
          <Sliders className="w-4 h-4" />
          <span>Research Preferences</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveSection('activity')}
          className={`px-3.5 py-2 rounded-lg text-xs font-medium flex items-center gap-2 whitespace-nowrap transition-colors ${
            activeSection === 'activity'
              ? 'bg-navy-800 text-white font-semibold shadow-xs'
              : 'text-ink-600 hover:text-ink-950 hover:bg-parchment-200/60'
          }`}
        >
          <Activity className="w-4 h-4" />
          <span>Usage & Activity</span>
        </button>
      </div>

      {/* SECTION 1: Account & Profile */}
      {activeSection === 'profile' && (
        <div className="space-y-6">
          <div className="p-6 bg-white rounded-xl border border-parchment-300 shadow-xs space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-parchment-200">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-reading-primary/10 border border-reading-primary/20 flex items-center justify-center text-reading-primary font-serif font-bold text-base">
                  {user?.display_name?.charAt(0).toUpperCase() || user?.email?.charAt(0).toUpperCase() || 'R'}
                </div>
                <div>
                  <h2 className="text-base font-serif font-bold text-ink-950">Researcher Identity</h2>
                  <p className="text-xs text-ink-500">Official profile attributes associated with this research account.</p>
                </div>
              </div>
              <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300 capitalize">
                {user?.status || 'Active'}
              </span>
            </div>

            <form onSubmit={handleSaveProfile} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                <div>
                  <label className="block text-ink-700 font-medium mb-1">Display Name</label>
                  <input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-parchment-300 bg-parchment-50 text-ink-950 focus:outline-hidden focus:ring-2 focus:ring-navy-600"
                    placeholder="Dr. Jane Doe"
                  />
                </div>
                <div>
                  <label className="block text-ink-700 font-medium mb-1">Registered Email</label>
                  <input
                    type="email"
                    value={user?.email || ''}
                    disabled
                    className="w-full px-3 py-2 rounded-lg border border-parchment-300 bg-parchment-100 text-ink-600 font-mono cursor-not-allowed"
                  />
                </div>
                <div>
                  <label className="block text-ink-700 font-medium mb-1">Account Role</label>
                  <div className="px-3 py-2 rounded-lg border border-parchment-200 bg-parchment-50 text-ink-900 font-medium capitalize">
                    {user?.role === 'admin' ? 'Administrator' : 'Academic Researcher'}
                  </div>
                </div>
                <div>
                  <label className="block text-ink-700 font-medium mb-1">Account Created</label>
                  <div className="px-3 py-2 rounded-lg border border-parchment-200 bg-parchment-50 text-ink-700 font-mono">
                    {user?.created_at ? new Date(user.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' }) : 'Verified Account'}
                  </div>
                </div>
              </div>

              {profileMessage && (
                <div
                  className={`p-3 rounded-lg text-xs flex items-center gap-2 ${
                    profileMessage.type === 'success'
                      ? 'bg-emerald-50 border border-emerald-200 text-emerald-800'
                      : 'bg-rose-50 border border-rose-200 text-rose-800'
                  }`}
                >
                  {profileMessage.type === 'success' ? (
                    <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
                  ) : (
                    <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
                  )}
                  <span>{profileMessage.text}</span>
                </div>
              )}

              <div className="flex justify-end pt-2">
                <button
                  type="submit"
                  disabled={profileSaving}
                  className="px-4 py-2 bg-navy-800 hover:bg-navy-900 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors disabled:opacity-50"
                >
                  <Save className="w-3.5 h-3.5" />
                  <span>{profileSaving ? 'Saving Changes...' : 'Save Profile'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* SECTION 2: Security & Privacy */}
      {activeSection === 'security' && (
        <div className="space-y-6">
          {/* Change Password Card */}
          <div className="p-6 bg-white rounded-xl border border-parchment-300 shadow-xs space-y-5">
            <div className="flex items-center gap-2.5 pb-3 border-b border-parchment-200">
              <Key className="w-5 h-5 text-navy-800" />
              <div>
                <h2 className="text-sm font-serif font-bold text-ink-950">Change Password</h2>
                <p className="text-xs text-ink-500">Update your account credentials using Argon2id encryption.</p>
              </div>
            </div>

            <form onSubmit={handleChangePassword} className="space-y-4 max-w-lg text-xs">
              <div>
                <label className="block text-ink-700 font-medium mb-1">Current Password</label>
                <input
                  type="password"
                  aria-label="Current Password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-parchment-300 bg-parchment-50 text-ink-950 focus:outline-hidden focus:ring-2 focus:ring-navy-600"
                  placeholder="••••••••••••"
                />
              </div>

              <div>
                <label className="block text-ink-700 font-medium mb-1">New Password (minimum 8 characters)</label>
                <input
                  type="password"
                  aria-label="New Password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-parchment-300 bg-parchment-50 text-ink-950 focus:outline-hidden focus:ring-2 focus:ring-navy-600"
                  placeholder="••••••••••••"
                />
              </div>

              <div>
                <label className="block text-ink-700 font-medium mb-1">Confirm New Password</label>
                <input
                  type="password"
                  aria-label="Confirm New Password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-parchment-300 bg-parchment-50 text-ink-950 focus:outline-hidden focus:ring-2 focus:ring-navy-600"
                  placeholder="••••••••••••"
                />
              </div>

              {passwordMessage && (
                <div
                  className={`p-3 rounded-lg text-xs flex items-center gap-2 ${
                    passwordMessage.type === 'success'
                      ? 'bg-emerald-50 border border-emerald-200 text-emerald-800'
                      : 'bg-rose-50 border border-rose-200 text-rose-800'
                  }`}
                >
                  {passwordMessage.type === 'success' ? (
                    <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
                  ) : (
                    <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
                  )}
                  <span>{passwordMessage.text}</span>
                </div>
              )}

              <button
                type="submit"
                disabled={passwordLoading}
                className="px-4 py-2 bg-navy-800 hover:bg-navy-900 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors disabled:opacity-50"
              >
                <Lock className="w-3.5 h-3.5" />
                <span>{passwordLoading ? 'Updating Password...' : 'Update Password'}</span>
              </button>
            </form>
          </div>

          {/* Active Sessions Card */}
          <div className="p-6 bg-white rounded-xl border border-parchment-300 shadow-xs space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-parchment-200">
              <div className="flex items-center gap-2.5">
                <Laptop className="w-5 h-5 text-navy-800" />
                <div>
                  <h2 className="text-sm font-serif font-bold text-ink-950">Active Login Sessions</h2>
                  <p className="text-xs text-ink-500">Currently recognized authentication tokens for your account.</p>
                </div>
              </div>
              {sessions.length > 1 && (
                <button
                  type="button"
                  onClick={handleRevokeOtherSessions}
                  disabled={revokingSessions}
                  className="px-3 py-1.5 border border-rose-300 hover:bg-rose-50 text-rose-700 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors disabled:opacity-50"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  <span>{revokingSessions ? 'Revoking...' : 'Revoke Other Sessions'}</span>
                </button>
              )}
            </div>

            {sessionMessage && (
              <div className="p-3 bg-parchment-100 rounded-lg text-xs text-ink-700 border border-parchment-200">
                {sessionMessage}
              </div>
            )}

            <div className="divide-y divide-parchment-200 border border-parchment-200 rounded-lg overflow-hidden text-xs">
              {sessions.length > 0 ? (
                sessions.map((sess) => (
                  <div key={sess.id} className="p-3 sm:p-3.5 flex items-center justify-between hover:bg-parchment-50 transition-colors">
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-semibold text-ink-900">{sess.ip_address || '127.0.0.1'}</span>
                        {sess.is_current ? (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
                            Current Session
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-parchment-200 text-ink-700">
                            Active
                          </span>
                        )}
                      </div>
                      <p className="text-ink-500 truncate max-w-xs sm:max-w-md">{sess.user_agent || 'Scholarly Web Client'}</p>
                    </div>
                    <div className="text-right text-[11px] text-ink-500 font-mono shrink-0 ml-3">
                      <p>Signed In: {new Date(sess.created_at).toLocaleDateString()}</p>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-4 text-center text-ink-500 italic">
                  No other active sessions. Current session is authenticated via secure HttpOnly cookie.
                </div>
              )}
            </div>
          </div>

          {/* Privacy & Document Isolation Card */}
          <div className="p-6 bg-white rounded-xl border border-parchment-300 shadow-xs space-y-4">
            <div className="flex items-center gap-2.5 pb-3 border-b border-parchment-200">
              <ShieldCheck className="w-5 h-5 text-forest-700" />
              <div>
                <h2 className="text-sm font-serif font-bold text-ink-950">Privacy & Document Isolation</h2>
                <p className="text-xs text-ink-500">Architectural guarantees ensuring zero cross-researcher data exposure.</p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div className="p-3.5 rounded-lg bg-parchment-50 border border-parchment-200 space-y-1">
                <span className="font-semibold text-ink-900 block">Strict Literature Vault Partitioning</span>
                <p className="text-ink-600 leading-relaxed">
                  Every uploaded PDF document, page extraction, text chunk, and vector embedding is strictly tied to your authenticated account ID.
                </p>
              </div>
              <div className="p-3.5 rounded-lg bg-parchment-50 border border-parchment-200 space-y-1">
                <span className="font-semibold text-ink-900 block">Isolated Vector & BM25 Retrieval</span>
                <p className="text-ink-600 leading-relaxed">
                  Hybrid semantic search queries filter strictly within your literature vault. Other researchers cannot retrieve or view your indexed papers.
                </p>
              </div>
              <div className="p-3.5 rounded-lg bg-parchment-50 border border-parchment-200 space-y-1">
                <span className="font-semibold text-ink-900 block">No Foundational Model Training</span>
                <p className="text-ink-600 leading-relaxed">
                  Your research excerpts are passed ephemerally to the Google Gemini API for factual synthesis only and are never retained for model training.
                </p>
              </div>
              <div className="p-3.5 rounded-lg bg-parchment-50 border border-parchment-200 space-y-1">
                <span className="font-semibold text-ink-900 block">Verifiable Provenance Grounding</span>
                <p className="text-ink-600 leading-relaxed">
                  All synthesized answers require exact bounding citations referencing your original PDFs, preventing fabricated citations.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SECTION 3: Storage & Uploads */}
      {activeSection === 'storage' && (
        <div className="space-y-6">
          <div className="p-6 bg-white rounded-xl border border-parchment-300 shadow-xs space-y-6">
            <div className="flex items-center justify-between pb-3 border-b border-parchment-200">
              <div className="flex items-center gap-2.5">
                <HardDrive className="w-5 h-5 text-navy-800" />
                <div>
                  <h2 className="text-sm font-serif font-bold text-ink-950">Storage & Upload Allocation</h2>
                  <p className="text-xs text-ink-500">Cumulative storage tracking against your standard 500 MB research pilot limit.</p>
                </div>
              </div>
              <span className="font-mono text-xs font-bold text-navy-900">
                {storageUsedMb.toFixed(2)} MB / {storageQuotaMb} MB ({storagePercent}%)
              </span>
            </div>

            {/* Quota Progress Bar */}
            <div className="space-y-2">
              <div className="w-full h-3 bg-parchment-200 rounded-full overflow-hidden border border-parchment-300">
                <div
                  className={`h-full transition-all duration-300 ${
                    storagePercent >= 90
                      ? 'bg-rose-500'
                      : storagePercent >= 75
                      ? 'bg-amber-500'
                      : 'bg-forest-600'
                  }`}
                  style={{ width: `${storagePercent}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-xs text-ink-500 font-medium">
                <span>{usage?.document_count || 0} indexed papers</span>
                <span>{remainingStorageMb.toFixed(2)} MB remaining</span>
              </div>
            </div>

            {/* Metric Row */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs pt-2">
              <div className="p-4 rounded-xl border border-parchment-200 bg-parchment-50/60">
                <span className="text-ink-500 block mb-1">Storage Consumed</span>
                <p className="text-xl font-bold font-serif text-ink-950">{storageUsedMb.toFixed(2)} MB</p>
                <p className="text-[11px] text-ink-400 mt-0.5">Across all papers</p>
              </div>
              <div className="p-4 rounded-xl border border-parchment-200 bg-parchment-50/60">
                <span className="text-ink-500 block mb-1">Total Quota</span>
                <p className="text-xl font-bold font-serif text-ink-950">{storageQuotaMb} MB</p>
                <p className="text-[11px] text-ink-400 mt-0.5">Standard pilot limit</p>
              </div>
              <div className="p-4 rounded-xl border border-parchment-200 bg-parchment-50/60">
                <span className="text-ink-500 block mb-1">Indexed Documents</span>
                <p className="text-xl font-bold font-serif text-ink-950">{usage?.document_count || 0}</p>
                <p className="text-[11px] text-ink-400 mt-0.5">{usage?.total_pages_ingested || 0} extracted pages</p>
              </div>
              <div className="p-4 rounded-xl border border-parchment-200 bg-parchment-50/60">
                <span className="text-ink-500 block mb-1">Maximum Upload</span>
                <p className="text-xl font-bold font-serif text-ink-950">{systemSettings?.max_upload_size_mb || 32} MB</p>
                <p className="text-[11px] text-ink-400 mt-0.5">Per technical PDF</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SECTION 4: Research Preferences */}
      {activeSection === 'preferences' && (
        <div className="space-y-6">
          <form onSubmit={handleSavePreferences} className="p-6 bg-white rounded-xl border border-parchment-300 shadow-xs space-y-6">
            <div className="flex items-center justify-between pb-3 border-b border-parchment-200">
              <div className="flex items-center gap-2.5">
                <Sliders className="w-5 h-5 text-navy-800" />
                <div>
                  <h2 className="text-sm font-serif font-bold text-ink-950">Scholarly Research Preferences</h2>
                  <p className="text-xs text-ink-500">Configure your default citation style, synthesis detail, and retrieval depth.</p>
                </div>
              </div>
              <button
                type="submit"
                className="px-3.5 py-1.5 bg-navy-800 hover:bg-navy-900 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors"
              >
                <Save className="w-3.5 h-3.5" />
                <span>Save Preferences</span>
              </button>
            </div>

            {prefsSavedMessage && (
              <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg text-xs flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>{prefsSavedMessage}</span>
              </div>
            )}

            <div className="space-y-5 text-xs">
              {/* Answer Style */}
              <div>
                <label className="block text-ink-800 font-semibold mb-1">Preferred Answer Style</label>
                <p className="text-ink-500 mb-2">Controls the default structural formatting for AI evidence synthesis.</p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {[
                    { id: 'comprehensive', title: 'Comprehensive Scholarly', desc: 'Detailed multi-paragraph prose with full contextual reasoning.' },
                    { id: 'concise', title: 'Concise Executive', desc: 'Direct, tightly focused summary answering the query immediately.' },
                    { id: 'bulleted', title: 'Structured Synthesis', desc: 'Key insights and enumerated claims formatted as structured bullets.' },
                  ].map((style) => (
                    <label
                      key={style.id}
                      className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                        preferences.preferredAnswerStyle === style.id
                          ? 'border-navy-700 bg-navy-50/60 ring-1 ring-navy-700'
                          : 'border-parchment-200 hover:border-parchment-300 bg-parchment-50/40'
                      }`}
                    >
                      <input
                        type="radio"
                        name="answerStyle"
                        value={style.id}
                        checked={preferences.preferredAnswerStyle === style.id}
                        onChange={() => setPreferences((p) => ({ ...p, preferredAnswerStyle: style.id as any }))}
                        className="sr-only"
                      />
                      <span className="font-semibold text-ink-950 block mb-0.5">{style.title}</span>
                      <span className="text-ink-500 text-[11px] leading-tight block">{style.desc}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Citation Display Preference */}
              <div>
                <label className="block text-ink-800 font-semibold mb-1">Citation Display Preference</label>
                <p className="text-ink-500 mb-2">How citations and source badges appear within verified answers.</p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {[
                    { id: 'inline_chips', title: 'Interactive Chips', desc: 'Inline clickable [cite:N] pills with one-click PDF viewer synchronization.' },
                    { id: 'footnotes', title: 'Footnotes Style', desc: 'Traditional superscript markers linking to bibliographic bottom notes.' },
                    { id: 'provenance_drawer', title: 'Side Inspector', desc: 'Always pin citations to the right-hand Evidence Inspector drawer.' },
                  ].map((cite) => (
                    <label
                      key={cite.id}
                      className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                        preferences.citationDisplayPreference === cite.id
                          ? 'border-navy-700 bg-navy-50/60 ring-1 ring-navy-700'
                          : 'border-parchment-200 hover:border-parchment-300 bg-parchment-50/40'
                      }`}
                    >
                      <input
                        type="radio"
                        name="citationDisplay"
                        value={cite.id}
                        checked={preferences.citationDisplayPreference === cite.id}
                        onChange={() => setPreferences((p) => ({ ...p, citationDisplayPreference: cite.id as any }))}
                        className="sr-only"
                      />
                      <span className="font-semibold text-ink-950 block mb-0.5">{cite.title}</span>
                      <span className="text-ink-500 text-[11px] leading-tight block">{cite.desc}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Default Retrieval Count (top_k) */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-ink-800 font-semibold">Default Retrieval Depth (Top-K Passages)</label>
                  <span className="font-mono font-bold text-navy-800">{preferences.defaultTopK} passages</span>
                </div>
                <p className="text-ink-500 mb-2">Number of hybrid fusion passages assembled for factual grounding (backend supported: 1 to 30).</p>
                <div className="flex items-center gap-3">
                  {[5, 8, 12, 16].map((k) => (
                    <button
                      key={k}
                      type="button"
                      onClick={() => setPreferences((p) => ({ ...p, defaultTopK: k }))}
                      className={`px-3.5 py-1.5 rounded-lg border text-xs font-mono font-medium transition-colors ${
                        preferences.defaultTopK === k
                          ? 'border-navy-700 bg-navy-800 text-white'
                          : 'border-parchment-300 bg-parchment-50 text-ink-700 hover:bg-parchment-100'
                      }`}
                    >
                      Top-{k} {k === 8 ? '(Default)' : ''}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </form>
        </div>
      )}

      {/* SECTION 5: Usage & Activity */}
      {activeSection === 'activity' && (
        <div className="space-y-6">
          <div className="p-6 bg-white rounded-xl border border-parchment-300 shadow-xs space-y-6">
            <div className="flex items-center justify-between pb-3 border-b border-parchment-200">
              <div className="flex items-center gap-2.5">
                <Activity className="w-5 h-5 text-navy-800" />
                <div>
                  <h2 className="text-sm font-serif font-bold text-ink-950">Workspace Usage & Activity Metrics</h2>
                  <p className="text-xs text-ink-500">Real-time measured operations and AI query utilization for your account.</p>
                </div>
              </div>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
              <div className="p-4 rounded-xl border border-parchment-200 bg-parchment-50/60">
                <div className="flex items-center gap-1.5 text-ink-500 mb-1">
                  <Cpu className="w-3.5 h-3.5 text-navy-700" />
                  <span>AI Queries</span>
                </div>
                <p className="text-xl font-bold font-serif text-ink-950">{usage?.llm_queries_executed || 0}</p>
                <p className="text-[11px] text-ink-400 mt-0.5">Synthesized answers</p>
              </div>

              <div className="p-4 rounded-xl border border-parchment-200 bg-parchment-50/60">
                <div className="flex items-center gap-1.5 text-ink-500 mb-1">
                  <Layers className="w-3.5 h-3.5 text-navy-700" />
                  <span>Token Volume</span>
                </div>
                <p className="text-xl font-bold font-serif text-ink-950">
                  {usage?.llm_tokens_consumed ? usage.llm_tokens_consumed.toLocaleString() : '0'}
                </p>
                <p className="text-[11px] text-ink-400 mt-0.5">Prompt + completion tokens</p>
              </div>

              <div className="p-4 rounded-xl border border-parchment-200 bg-parchment-50/60">
                <div className="flex items-center gap-1.5 text-ink-500 mb-1">
                  <FileText className="w-3.5 h-3.5 text-navy-700" />
                  <span>Indexed Papers</span>
                </div>
                <p className="text-xl font-bold font-serif text-ink-950">{usage?.document_count || 0}</p>
                <p className="text-[11px] text-ink-400 mt-0.5">{usage?.total_chunks_indexed || 0} vector chunks</p>
              </div>

              <div className="p-4 rounded-xl border border-parchment-200 bg-parchment-50/60">
                <div className="flex items-center gap-1.5 text-ink-500 mb-1">
                  <HardDrive className="w-3.5 h-3.5 text-navy-700" />
                  <span>Storage Used</span>
                </div>
                <p className="text-xl font-bold font-serif text-ink-950">{storageUsedMb.toFixed(1)} MB</p>
                <p className="text-[11px] text-ink-400 mt-0.5">of {storageQuotaMb} MB limit</p>
              </div>
            </div>

            {/* Account Activity Summary */}
            <div className="p-4 rounded-xl bg-parchment-50/70 border border-parchment-200 space-y-2 text-xs">
              <span className="font-semibold text-ink-900 block">Activity Summary</span>
              <p className="text-ink-600 leading-relaxed">
                Your workspace currently holds {usage?.document_count || 0} papers across {usage?.collection_count || 0} collections and {usage?.note_count || 0} research notes. All actions, uploads, and AI queries are logged strictly for your session provenance.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
