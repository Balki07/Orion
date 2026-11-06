import React, { useState, useEffect } from 'react';
import {
  X,
  HardDrive,
  Cpu,
  LogIn,
  Clock,
  Shield,
  FileText,
  CheckCircle2,
  XCircle,
  Calendar,
  Layers,
} from 'lucide-react';
import { AdminUserSummary, AdminUserDetailResponse } from '../../types';
import { api } from '../../services/api';

interface AdminUserDetailModalProps {
  user: AdminUserSummary | null;
  onClose: () => void;
}

export const AdminUserDetailModal: React.FC<AdminUserDetailModalProps> = ({ user, onClose }) => {
  const [detail, setDetail] = useState<AdminUserDetailResponse | null>(null);
  const [activity, setActivity] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'documents' | 'logins' | 'activity'>('overview');

  // Close on Escape key press
  useEffect(() => {
    if (!user) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [user, onClose]);

  useEffect(() => {
    if (!user) return;
    let isMounted = true;
    setLoading(true);

    Promise.all([
      api.getAdminUserDetail(user.id),
      api.getAdminUserActivity(user.id, 25),
    ])
      .then(([detailData, activityData]) => {
        if (isMounted) {
          setDetail(detailData);
          setActivity(activityData);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error('Failed to load researcher detail:', err);
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [user]);

  if (!user) return null;

  const quotaPercent = Math.min(
    Math.round(((user.storage_used_mb || 0) / (user.storage_quota_mb || 500)) * 100),
    100
  );

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="admin-user-detail-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 md:p-6 bg-slate-950/45 dark:bg-black/60 backdrop-blur-[6px] animate-in fade-in duration-200"
    >
      <div className="relative w-full max-w-4xl max-h-[92vh] sm:max-h-[88vh] bg-[#FFFCF5]/95 dark:bg-[#151F1E]/95 backdrop-blur-md rounded-xl shadow-2xl shadow-navy-950/20 dark:shadow-black/60 border border-parchment-300 dark:border-[#273634] flex flex-col overflow-hidden text-ink dark:text-slate-100">
        {/* Header */}
        <div className="flex items-center justify-between px-5 sm:px-6 py-4 border-b border-parchment-200 dark:border-[#273634] bg-parchment-100/90 dark:bg-[#1A2524]/90 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 sm:w-11 sm:h-11 rounded-full bg-navy-100 dark:bg-navy-900/60 border border-navy-300 dark:border-navy-700 flex items-center justify-center text-navy-800 dark:text-navy-200 font-serif font-bold text-lg shrink-0 shadow-xs">
              {user.display_name?.charAt(0).toUpperCase() || user.email.charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 id="admin-user-detail-title" className="font-serif text-lg sm:text-xl font-bold text-navy-950 dark:text-white leading-tight truncate">
                  {user.display_name}
                </h3>
                <span
                  className={`px-2.5 py-0.5 text-xs font-semibold rounded-full border ${
                    user.role === 'admin'
                      ? 'bg-amber-100/80 text-amber-900 dark:bg-amber-950/60 dark:text-amber-200 border-amber-300 dark:border-amber-700/60'
                      : 'bg-emerald-100/80 text-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-200 border-emerald-300 dark:border-emerald-700/60'
                  }`}
                >
                  {user.role === 'admin' ? 'Administrator' : 'Researcher'}
                </span>
                <span
                  className={`px-2 py-0.5 text-xs font-semibold rounded-full border ${
                    user.is_active
                      ? 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800/50'
                      : 'bg-rose-50 text-rose-800 dark:bg-rose-950/40 dark:text-rose-300 border-rose-200 dark:border-rose-800/50'
                  }`}
                >
                  {user.status}
                </span>
              </div>
              <p className="text-xs text-ink-600 dark:text-slate-400 mt-0.5 font-mono truncate">
                {user.email} • ID: {user.id}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close modal"
            className="p-1.5 sm:p-2 rounded-lg text-ink-500 hover:text-navy-900 dark:text-slate-400 dark:hover:text-white hover:bg-parchment-200/80 dark:hover:bg-zinc-800 transition-colors focus:outline-hidden focus:ring-2 focus:ring-navy-600 shrink-0"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Navigation Tabs */}
        <div className="flex items-center gap-2 sm:gap-6 px-5 sm:px-6 border-b border-parchment-200 dark:border-[#273634] bg-parchment-50/90 dark:bg-[#151F1E]/90 text-xs sm:text-sm font-medium overflow-x-auto shrink-0">
          <button
            type="button"
            onClick={() => setActiveTab('overview')}
            className={`py-3 border-b-2 whitespace-nowrap transition-colors focus:outline-hidden ${
              activeTab === 'overview'
                ? 'border-navy-700 text-navy-950 dark:border-blue-400 dark:text-white font-semibold'
                : 'border-transparent text-ink-600 hover:text-navy-900 dark:text-slate-400 dark:hover:text-white'
            }`}
          >
            Overview & Storage
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('documents')}
            className={`py-3 border-b-2 whitespace-nowrap transition-colors focus:outline-hidden ${
              activeTab === 'documents'
                ? 'border-navy-700 text-navy-950 dark:border-blue-400 dark:text-white font-semibold'
                : 'border-transparent text-ink-600 hover:text-navy-900 dark:text-slate-400 dark:hover:text-white'
            }`}
          >
            Documents ({detail?.recent_documents.length || 0})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('logins')}
            className={`py-3 border-b-2 whitespace-nowrap transition-colors focus:outline-hidden ${
              activeTab === 'logins'
                ? 'border-navy-700 text-navy-950 dark:border-blue-400 dark:text-white font-semibold'
                : 'border-transparent text-ink-600 hover:text-navy-900 dark:text-slate-400 dark:hover:text-white'
            }`}
          >
            Login Audits ({detail?.recent_logins.length || 0})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('activity')}
            className={`py-3 border-b-2 whitespace-nowrap transition-colors focus:outline-hidden ${
              activeTab === 'activity'
                ? 'border-navy-700 text-navy-950 dark:border-blue-400 dark:text-white font-semibold'
                : 'border-transparent text-ink-600 hover:text-navy-900 dark:text-slate-400 dark:hover:text-white'
            }`}
          >
            Unified Activity Feed
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12 text-ink-600 dark:text-slate-400">
              <div className="w-8 h-8 border-2 border-navy-700 dark:border-blue-400 border-t-transparent rounded-full animate-spin mb-3"></div>
              <p className="text-sm font-medium">Retrieving researcher audit trail and storage metrics...</p>
            </div>
          ) : (
            <>
              {activeTab === 'overview' && (
                <div className="space-y-6">
                  {/* Quota Gauge Card */}
                  <div className="p-4 sm:p-5 rounded-xl border border-parchment-200 dark:border-[#273634] bg-white/95 dark:bg-[#1B2625]/95 shadow-xs space-y-3">
                    <div className="flex items-center justify-between text-xs sm:text-sm">
                      <div className="flex items-center gap-2 font-semibold text-navy-900 dark:text-white">
                        <HardDrive className="w-4 h-4 text-navy-700 dark:text-blue-400 shrink-0" />
                        <span>Cumulative Storage Quota (500 MB Standard)</span>
                      </div>
                      <span className="font-mono font-bold text-navy-950 dark:text-white">
                        {user.storage_used_mb.toFixed(2)} MB / {user.storage_quota_mb} MB ({quotaPercent}%)
                      </span>
                    </div>
                    <div className="w-full h-3 bg-parchment-200 dark:bg-zinc-800 rounded-full overflow-hidden border border-parchment-300 dark:border-zinc-700">
                      <div
                        className={`h-full transition-all duration-300 ${
                          quotaPercent >= 90
                            ? 'bg-rose-500'
                            : quotaPercent >= 75
                            ? 'bg-amber-500'
                            : 'bg-emerald-600'
                        }`}
                        style={{ width: `${quotaPercent}%` }}
                      ></div>
                    </div>
                    <div className="flex items-center justify-between text-xs text-ink-600 dark:text-slate-400 font-medium">
                      <span>{user.document_count} uploaded documents</span>
                      <span>{(user.storage_quota_mb - user.storage_used_mb).toFixed(2)} MB remaining</span>
                    </div>
                  </div>

                  {/* Summary Metric Grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
                    <div className="p-3.5 sm:p-4 rounded-xl border border-parchment-200 dark:border-[#273634] bg-white/95 dark:bg-[#1B2625]/95 shadow-xs">
                      <div className="flex items-center gap-1.5 text-ink-600 dark:text-slate-400 text-xs mb-1.5 font-medium">
                        <LogIn className="w-3.5 h-3.5 text-navy-700 dark:text-blue-400" />
                        <span>Login Sessions</span>
                      </div>
                      <p className="text-xl sm:text-2xl font-bold font-serif text-navy-950 dark:text-white">{user.login_count}</p>
                      <p className="text-[11px] text-ink-500 dark:text-slate-400 mt-1">
                        Active now: {detail?.active_sessions_count || 0}
                      </p>
                    </div>

                    <div className="p-3.5 sm:p-4 rounded-xl border border-parchment-200 dark:border-[#273634] bg-white/95 dark:bg-[#1B2625]/95 shadow-xs">
                      <div className="flex items-center gap-1.5 text-ink-600 dark:text-slate-400 text-xs mb-1.5 font-medium">
                        <Cpu className="w-3.5 h-3.5 text-navy-700 dark:text-blue-400" />
                        <span>AI Queries</span>
                      </div>
                      <p className="text-xl sm:text-2xl font-bold font-serif text-navy-950 dark:text-white">{user.ai_request_count}</p>
                      <p className="text-[11px] text-ink-500 dark:text-slate-400 mt-1">
                        {user.ai_total_tokens.toLocaleString()} tokens
                      </p>
                    </div>

                    <div className="p-3.5 sm:p-4 rounded-xl border border-parchment-200 dark:border-[#273634] bg-white/95 dark:bg-[#1B2625]/95 shadow-xs">
                      <div className="flex items-center gap-1.5 text-ink-600 dark:text-slate-400 text-xs mb-1.5 font-medium">
                        <Calendar className="w-3.5 h-3.5 text-navy-700 dark:text-blue-400" />
                        <span>Registered On</span>
                      </div>
                      <p className="text-sm font-semibold text-navy-950 dark:text-white mt-1">
                        {new Date(user.created_at).toLocaleDateString()}
                      </p>
                      <p className="text-[11px] text-ink-500 dark:text-slate-400 mt-0.5 font-mono">
                        {new Date(user.created_at).toLocaleTimeString()}
                      </p>
                    </div>

                    <div className="p-3.5 sm:p-4 rounded-xl border border-parchment-200 dark:border-[#273634] bg-white/95 dark:bg-[#1B2625]/95 shadow-xs">
                      <div className="flex items-center gap-1.5 text-ink-600 dark:text-slate-400 text-xs mb-1.5 font-medium">
                        <Clock className="w-3.5 h-3.5 text-navy-700 dark:text-blue-400" />
                        <span>Last Active</span>
                      </div>
                      <p className="text-sm font-semibold text-navy-950 dark:text-white mt-1">
                        {user.last_login_at
                          ? new Date(user.last_login_at).toLocaleDateString()
                          : 'No login recorded'}
                      </p>
                      <p className="text-[11px] text-ink-500 dark:text-slate-400 mt-0.5 font-mono">
                        {user.last_login_at ? new Date(user.last_login_at).toLocaleTimeString() : 'N/A'}
                      </p>
                    </div>
                  </div>

                  {/* Active Sessions List */}
                  <div className="space-y-3">
                    <h4 className="text-sm font-semibold font-serif text-navy-950 dark:text-white flex items-center gap-2">
                      <Layers className="w-4 h-4 text-navy-700 dark:text-blue-400" />
                      <span>Recent Authentication Sessions</span>
                    </h4>
                    {detail?.recent_sessions && detail.recent_sessions.length > 0 ? (
                      <div className="divide-y divide-parchment-200 dark:divide-[#273634] border border-parchment-200 dark:border-[#273634] rounded-xl overflow-hidden bg-white/95 dark:bg-[#1B2625]/95 shadow-xs">
                        {detail.recent_sessions.map((s) => (
                          <div key={s.id} className="p-3 sm:p-3.5 flex items-center justify-between text-xs hover:bg-parchment-50/60 dark:hover:bg-[#202D2C]/60 transition-colors">
                            <div className="space-y-0.5 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="font-mono font-semibold text-navy-950 dark:text-white">{s.ip_address || '127.0.0.1'}</span>
                                <span
                                  className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                                    s.is_active
                                      ? 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950/70 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                                      : 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-400 border-zinc-200 dark:border-zinc-700'
                                  }`}
                                >
                                  {s.is_active ? 'Active' : 'Expired/Revoked'}
                                </span>
                              </div>
                              <p className="text-ink-600 dark:text-slate-400 truncate max-w-xs sm:max-w-md">{s.user_agent || 'Unknown Client'}</p>
                            </div>
                            <div className="text-right text-[11px] text-ink-500 dark:text-slate-400 font-mono shrink-0 ml-3">
                              <p>Issued: {new Date(s.created_at).toLocaleDateString()}</p>
                              <p>Expires: {new Date(s.expires_at).toLocaleDateString()}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-ink-500 dark:text-slate-400 italic">No active sessions found.</p>
                    )}
                  </div>
                </div>
              )}

              {activeTab === 'documents' && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-semibold font-serif text-navy-950 dark:text-white">Indexed Research Literature</h4>
                    <span className="text-xs font-mono text-ink-600 dark:text-slate-400">
                      Cumulative: {user.storage_used_mb.toFixed(2)} MB of {user.storage_quota_mb} MB
                    </span>
                  </div>
                  {detail?.recent_documents && detail.recent_documents.length > 0 ? (
                    <div className="border border-parchment-200 dark:border-[#273634] rounded-xl overflow-hidden bg-white/95 dark:bg-[#1B2625]/95 shadow-xs">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-parchment-100/90 dark:bg-[#202D2C]/90 border-b border-parchment-200 dark:border-[#273634] text-ink-600 dark:text-slate-300 font-medium">
                          <tr>
                            <th className="py-2.5 px-3">Filename</th>
                            <th className="py-2.5 px-3">Size</th>
                            <th className="py-2.5 px-3">Status</th>
                            <th className="py-2.5 px-3 text-right">Uploaded</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-parchment-200 dark:divide-[#273634]">
                          {detail.recent_documents.map((d) => (
                            <tr key={d.id} className="hover:bg-parchment-50/70 dark:hover:bg-[#202D2C]/70 transition-colors">
                              <td className="py-2.5 px-3 font-medium text-navy-950 dark:text-white flex items-center gap-2">
                                <FileText className="w-3.5 h-3.5 text-navy-700 dark:text-blue-400 flex-shrink-0" />
                                <span className="truncate max-w-xs">{d.title}</span>
                              </td>
                              <td className="py-2.5 px-3 text-ink-600 dark:text-slate-400 font-mono">
                                {(d.file_size_bytes / (1024 * 1024)).toFixed(2)} MB
                              </td>
                              <td className="py-2.5 px-3">
                                <span
                                  className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                                    d.status === 'completed'
                                      ? 'bg-emerald-100/80 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800'
                                      : d.status === 'failed'
                                      ? 'bg-rose-100/80 text-rose-900 dark:bg-rose-950/40 dark:text-rose-300 border-rose-300 dark:border-rose-800'
                                      : 'bg-amber-100/80 text-amber-900 dark:bg-amber-950/40 dark:text-amber-300 border-amber-300 dark:border-amber-800'
                                  }`}
                                >
                                  {d.status}
                                </span>
                              </td>
                              <td className="py-2.5 px-3 text-right text-ink-600 dark:text-slate-400 font-mono">
                                {new Date(d.created_at).toLocaleDateString()}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-center py-8 text-ink-500 dark:text-slate-400 text-xs italic bg-white/95 dark:bg-[#1B2625]/95 rounded-xl border border-parchment-200 dark:border-[#273634]">
                      No documents uploaded yet by this researcher.
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'logins' && (
                <div className="space-y-3">
                  <h4 className="text-sm font-semibold font-serif text-navy-950 dark:text-white">Recent Authentication Audit Events</h4>
                  {detail?.recent_logins && detail.recent_logins.length > 0 ? (
                    <div className="border border-parchment-200 dark:border-[#273634] rounded-xl overflow-hidden bg-white/95 dark:bg-[#1B2625]/95 shadow-xs">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-parchment-100/90 dark:bg-[#202D2C]/90 border-b border-parchment-200 dark:border-[#273634] text-ink-600 dark:text-slate-300 font-medium">
                          <tr>
                            <th className="py-2.5 px-3">Event</th>
                            <th className="py-2.5 px-3">Status</th>
                            <th className="py-2.5 px-3">IP Address</th>
                            <th className="py-2.5 px-3">Detail / Reason</th>
                            <th className="py-2.5 px-3 text-right">Timestamp</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-parchment-200 dark:divide-[#273634]">
                          {detail.recent_logins.map((evt) => (
                            <tr key={evt.id} className="hover:bg-parchment-50/70 dark:hover:bg-[#202D2C]/70 transition-colors">
                              <td className="py-2.5 px-3 font-semibold text-navy-950 dark:text-white capitalize">
                                {evt.event_type.replace('_', ' ')}
                              </td>
                              <td className="py-2.5 px-3">
                                {evt.success ? (
                                  <span className="flex items-center gap-1 text-emerald-700 dark:text-emerald-400 font-semibold">
                                    <CheckCircle2 className="w-3.5 h-3.5" />
                                    <span>Success</span>
                                  </span>
                                ) : (
                                  <span className="flex items-center gap-1 text-rose-700 dark:text-rose-400 font-semibold">
                                    <XCircle className="w-3.5 h-3.5" />
                                    <span>Failed</span>
                                  </span>
                                )}
                              </td>
                              <td className="py-2.5 px-3 font-mono text-ink-600 dark:text-slate-400">
                                {evt.ip_address || '—'}
                              </td>
                              <td className="py-2.5 px-3 text-ink-600 dark:text-slate-400">
                                {evt.failure_reason || (evt.success ? 'Normal Auth' : '—')}
                              </td>
                              <td className="py-2.5 px-3 text-right text-ink-600 dark:text-slate-400 font-mono">
                                {new Date(evt.created_at).toLocaleString()}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-center py-8 text-ink-500 dark:text-slate-400 text-xs italic bg-white/95 dark:bg-[#1B2625]/95 rounded-xl border border-parchment-200 dark:border-[#273634]">
                      No authentication events recorded.
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'activity' && (
                <div className="space-y-3">
                  <h4 className="text-sm font-semibold font-serif text-navy-950 dark:text-white">Chronological Researcher Activity</h4>
                  {activity.length > 0 ? (
                    <div className="space-y-2">
                      {activity.map((act) => (
                        <div
                          key={act.id}
                          className="p-3.5 rounded-xl border border-parchment-200 dark:border-[#273634] bg-white/95 dark:bg-[#1B2625]/95 shadow-xs flex items-start justify-between text-xs hover:bg-parchment-50/60 dark:hover:bg-[#202D2C]/60 transition-colors"
                        >
                          <div className="flex items-start gap-2.5 min-w-0">
                            <div className="p-2 rounded-lg bg-navy-50 text-navy-700 dark:bg-navy-950/60 dark:text-blue-300 mt-0.5 border border-navy-100 dark:border-navy-900 shrink-0">
                              {act.type === 'auth' ? (
                                <LogIn className="w-3.5 h-3.5" />
                              ) : act.type === 'document' ? (
                                <FileText className="w-3.5 h-3.5" />
                              ) : (
                                <Cpu className="w-3.5 h-3.5" />
                              )}
                            </div>
                            <div className="min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="font-semibold capitalize text-navy-950 dark:text-white">
                                  {act.action.replace('_', ' ')}
                                </span>
                                <span
                                  className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                                    act.success
                                      ? 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950/70 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                                      : 'bg-rose-100 text-rose-900 dark:bg-rose-950/70 dark:text-rose-300 border-rose-200 dark:border-rose-800'
                                  }`}
                                >
                                  {act.success ? 'OK' : 'Failed'}
                                </span>
                              </div>
                              <p className="text-ink-600 dark:text-slate-400 mt-0.5 truncate">
                                {act.type === 'document'
                                  ? `${act.details?.filename} • ${(act.details?.file_size / 1024 / 1024).toFixed(2)} MB`
                                  : act.type === 'ai_query'
                                  ? `Model: ${act.details?.model} • ${act.details?.tokens} tokens • ${act.details?.latency_ms?.toFixed(0)} ms`
                                  : `Client IP: ${act.ip_address || '127.0.0.1'}`}
                              </p>
                            </div>
                          </div>
                          <span className="text-ink-500 dark:text-slate-400 whitespace-nowrap text-[11px] font-mono ml-3 shrink-0">
                            {new Date(act.timestamp).toLocaleString()}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8 text-ink-500 dark:text-slate-400 text-xs italic bg-white/95 dark:bg-[#1B2625]/95 rounded-xl border border-parchment-200 dark:border-[#273634]">
                      No activity recorded for this researcher yet.
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 sm:px-6 py-3.5 border-t border-parchment-200 dark:border-[#273634] bg-parchment-100/90 dark:bg-[#1A2524]/90 flex items-center justify-between text-xs text-ink-600 dark:text-slate-400 shrink-0">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-navy-700 dark:text-blue-400 shrink-0" />
            <span className="truncate">Encrypted researcher audit log • Private document excerpts are strictly isolated</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-parchment-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 hover:bg-parchment-50 dark:hover:bg-zinc-700 text-navy-950 dark:text-white text-xs font-semibold transition-colors shadow-xs focus:outline-hidden focus:ring-2 focus:ring-navy-600 ml-4 shrink-0"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
