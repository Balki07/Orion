import React, { useState, useEffect, useCallback } from 'react';
import {
  ShieldAlert,
  Users,
  LogIn,
  HardDrive,
  Cpu,
  Activity,
  RefreshCw,
  Search,
  Filter,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Database,
  Server,
  Zap,
  BarChart3,
  Calendar,
  Lock,
  UserCheck,
  UserX,
  Key,
  Copy,
  Check,
  Trash2,
  Plus,
  Mail,
  Clock,
  Shield,
  Send,
  X,
} from 'lucide-react';
import {
  AdminOverviewResponse,
  AdminUserSummary,
  AdminUserListResponse,
  AdminSystemHealth,
  AdminTimeSeriesPoint,
  AdminLoginTimeSeriesPoint,
  AdminDailyAIUsagePoint,
  AccessRequestItem,
  InvitationItem,
} from '../../types';
import { api } from '../../services/api';
import { AdminUserDetailModal } from './AdminUserDetailModal';
import { AdminSystemDiagnosticsView } from './AdminSystemDiagnosticsView';

export const AdminDashboardView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'overview' | 'researchers' | 'access_requests' | 'health' | 'logins'>('overview');
  const [overview, setOverview] = useState<AdminOverviewResponse | null>(null);
  const [systemHealth, setSystemHealth] = useState<AdminSystemHealth | null>(null);

  // Researchers state
  const [usersList, setUsersList] = useState<AdminUserSummary[]>([]);
  const [usersTotal, setUsersTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [pageSize] = useState<number>(15);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [roleFilter, setRoleFilter] = useState<string>('');
  const [selectedUser, setSelectedUser] = useState<AdminUserSummary | null>(null);

  // Access Requests & Invitations state
  const [accessRequests, setAccessRequests] = useState<AccessRequestItem[]>([]);
  const [invitations, setInvitations] = useState<InvitationItem[]>([]);
  const [requestFilter, setRequestFilter] = useState<'all' | 'pending' | 'approved' | 'rejected'>('all');
  const [accessRequestsLoading, setAccessRequestsLoading] = useState<boolean>(false);
  const [invitationsLoading, setInvitationsLoading] = useState<boolean>(false);

  // Action modals & feedback state
  const [rejectModalReq, setRejectModalReq] = useState<AccessRequestItem | null>(null);
  const [rejectReason, setRejectReason] = useState<string>('');
  const [directInvModalOpen, setDirectInvModalOpen] = useState<boolean>(false);
  const [directInvUserId, setDirectInvUserId] = useState<string>('');
  const [directInvDays, setDirectInvDays] = useState<number>(7);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [oneTimeTokenData, setOneTimeTokenData] = useState<{
    token: string;
    email: string;
    expiresAt: string;
  } | null>(null);
  const [tokenCopied, setTokenCopied] = useState<boolean>(false);
  const [linkCopied, setLinkCopied] = useState<boolean>(false);
  const [actionSuccessMessage, setActionSuccessMessage] = useState<string | null>(null);

  // Analytics time series
  const [registrationSeries, setRegistrationSeries] = useState<AdminTimeSeriesPoint[]>([]);
  const [loginSeries, setLoginSeries] = useState<AdminLoginTimeSeriesPoint[]>([]);
  const [aiSeries, setAiSeries] = useState<AdminDailyAIUsagePoint[]>([]);

  // Loading & error
  const [loading, setLoading] = useState<boolean>(true);
  const [tableLoading, setTableLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());

  // Load overview and system health
  const loadDashboardData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ovData, healthData, regData, logData, aiData] = await Promise.all([
        api.getAdminOverview(),
        api.getAdminSystemHealth(),
        api.getAdminRegistrationAnalytics(14),
        api.getAdminLoginAnalytics(14),
        api.getAdminAIUsageAnalytics(14),
      ]);
      setOverview(ovData);
      setSystemHealth(healthData);
      setRegistrationSeries(regData);
      setLoginSeries(logData);
      setAiSeries(aiData);
      setLastRefreshed(new Date());
    } catch (err: any) {
      console.error('Failed to load admin dashboard data:', err);
      setError(err?.message || 'Failed to authenticate administrative oversight console.');
    } finally {
      setLoading(false);
    }
  }, []);

  // Load researchers table
  const loadResearchers = useCallback(async () => {
    setTableLoading(true);
    try {
      const res: AdminUserListResponse = await api.getAdminUsers({
        search: search || undefined,
        status: statusFilter || undefined,
        role: roleFilter || undefined,
        page,
        page_size: pageSize,
      });
      setUsersList(res.users);
      setUsersTotal(res.total);
      setTotalPages(res.total_pages);
    } catch (err: any) {
      console.error('Failed to load researchers list:', err);
    } finally {
      setTableLoading(false);
    }
  }, [search, statusFilter, roleFilter, page, pageSize]);

  // Load access requests
  const loadAccessRequests = useCallback(async () => {
    setAccessRequestsLoading(true);
    try {
      const data = await api.getAdminAccessRequests();
      setAccessRequests(data);
    } catch (err: any) {
      console.error('Failed to load access requests:', err);
    } finally {
      setAccessRequestsLoading(false);
    }
  }, []);

  // Load invitations
  const loadInvitations = useCallback(async () => {
    setInvitationsLoading(true);
    try {
      const data = await api.getAdminInvitations();
      setInvitations(data);
    } catch (err: any) {
      console.error('Failed to load invitations:', err);
    } finally {
      setInvitationsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  useEffect(() => {
    if (activeTab === 'researchers') {
      loadResearchers();
    } else if (activeTab === 'access_requests') {
      loadAccessRequests();
      loadInvitations();
      loadResearchers();
    }
  }, [activeTab, loadResearchers, loadAccessRequests, loadInvitations]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadResearchers();
  };

  // Access Control Handlers
  const handleApproveRequest = async (req: AccessRequestItem) => {
    setActionLoading(true);
    setError(null);
    try {
      const res = await api.approveAccessRequest(req.id, 7);
      setOneTimeTokenData({
        token: res.invitation_token || '',
        email: res.user_email || req.user_email || 'Researcher',
        expiresAt: res.expires_at,
      });
      setTokenCopied(false);
      setLinkCopied(false);
      setActionSuccessMessage(`Access request approved for ${req.user_email || 'researcher'}.`);
      loadAccessRequests();
      loadInvitations();
      loadDashboardData();
    } catch (err: any) {
      setError(err?.message || 'Failed to approve access request.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleConfirmReject = async () => {
    if (!rejectModalReq) return;
    if (!rejectReason.trim()) {
      setError('Please provide a rejection reason for the researcher.');
      return;
    }
    setActionLoading(true);
    try {
      await api.rejectAccessRequest(rejectModalReq.id, rejectReason.trim());
      setActionSuccessMessage(`Access request rejected.`);
      setRejectModalReq(null);
      setRejectReason('');
      loadAccessRequests();
      loadDashboardData();
    } catch (err: any) {
      setError(err?.message || 'Failed to reject access request.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDirectCreateInvitation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!directInvUserId) {
      setError('Please select a researcher account.');
      return;
    }
    setActionLoading(true);
    try {
      const targetUser = usersList.find((u) => u.id === directInvUserId);
      const res = await api.createAdminInvitation(directInvUserId, directInvDays);
      setOneTimeTokenData({
        token: res.invitation_token || '',
        email: res.user_email || targetUser?.email || 'Researcher',
        expiresAt: res.expires_at,
      });
      setTokenCopied(false);
      setLinkCopied(false);
      setDirectInvModalOpen(false);
      setDirectInvUserId('');
      setActionSuccessMessage('Direct invitation generated.');
      loadInvitations();
      loadAccessRequests();
      loadResearchers();
    } catch (err: any) {
      setError(err?.message || 'Failed to create invitation.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteInvitation = async (invitationId: string) => {
    if (!window.confirm('Are you sure you want to revoke/cancel this invitation?')) return;
    try {
      await api.deleteAdminInvitation(invitationId);
      setActionSuccessMessage('Invitation revoked.');
      loadInvitations();
    } catch (err: any) {
      setError(err?.message || 'Failed to delete invitation.');
    }
  };

  const handleRevokeUser = async (userId: string, email: string) => {
    if (!window.confirm(`Revoke research access for ${email}? Active sessions will be immediately terminated.`)) return;
    try {
      await api.revokeUserAccess(userId, 'Revoked by administrator from console');
      setActionSuccessMessage(`Access revoked for ${email}.`);
      loadResearchers();
      loadDashboardData();
    } catch (err: any) {
      setError(err?.message || 'Failed to revoke user access.');
    }
  };

  const handleReactivateUser = async (userId: string, email: string) => {
    try {
      await api.reactivateUserAccess(userId, 'Reactivated by administrator');
      setActionSuccessMessage(`Access reactivated for ${email}.`);
      loadResearchers();
      loadDashboardData();
    } catch (err: any) {
      setError(err?.message || 'Failed to reactivate user access.');
    }
  };

  const handleDirectActivateUser = async (userId: string, email: string) => {
    try {
      await api.directActivateUser(userId);
      setActionSuccessMessage(`Researcher ${email} directly activated.`);
      loadResearchers();
      loadDashboardData();
    } catch (err: any) {
      setError(err?.message || 'Failed to activate user account.');
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-surface-primary text-text-primary overflow-y-auto">
      {/* Top Banner & Header */}
      <div className="border-b border-border-primary bg-surface-secondary/40 px-8 py-5">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 max-w-7xl mx-auto">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                <ShieldAlert className="w-5 h-5" />
              </div>
              <h1 className="text-2xl font-serif font-bold text-text-primary tracking-tight">
                Administrator Oversight Console
              </h1>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300 dark:border-amber-700">
                Authorized Personnel Only
              </span>
            </div>
            <p className="text-xs text-text-secondary mt-1">
              Real-time monitoring of registered researchers, login security audit trails, cumulative 500 MB quotas, and Gemini AI operations.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-xs text-text-secondary hidden md:inline">
              Synced: {lastRefreshed.toLocaleTimeString()}
            </span>
            <button
              onClick={() => {
                loadDashboardData();
                if (activeTab === 'researchers') loadResearchers();
                if (activeTab === 'access_requests') {
                  loadAccessRequests();
                  loadInvitations();
                }
              }}
              disabled={loading}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg border border-border-secondary bg-surface-primary hover:bg-surface-tertiary text-text-primary text-xs font-medium transition-colors shadow-sm disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              <span>Refresh Metrics</span>
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-6 mt-6 max-w-7xl mx-auto border-b border-border-primary text-sm font-medium">
          <button
            onClick={() => setActiveTab('overview')}
            className={`py-3 border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === 'overview'
                ? 'border-accent-primary text-accent-primary font-semibold'
                : 'border-transparent text-text-secondary hover:text-text-primary'
            }`}
          >
            <BarChart3 className="w-4 h-4" />
            <span>Executive Overview</span>
          </button>
          <button
            onClick={() => setActiveTab('researchers')}
            className={`py-3 border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === 'researchers'
                ? 'border-accent-primary text-accent-primary font-semibold'
                : 'border-transparent text-text-secondary hover:text-text-primary'
            }`}
          >
            <Users className="w-4 h-4" />
            <span>Researcher Directory ({overview?.users.total_users || 0})</span>
          </button>
          <button
            onClick={() => setActiveTab('access_requests')}
            className={`py-3 border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === 'access_requests'
                ? 'border-accent-primary text-accent-primary font-semibold'
                : 'border-transparent text-text-secondary hover:text-text-primary'
            }`}
          >
            <UserCheck className="w-4 h-4" />
            <span>Access Requests &amp; Invitations</span>
            {accessRequests.filter((r) => r.status === 'pending').length > 0 && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-amber-500 text-white">
                {accessRequests.filter((r) => r.status === 'pending').length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('health')}
            className={`py-3 border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === 'health'
                ? 'border-accent-primary text-accent-primary font-semibold'
                : 'border-transparent text-text-secondary hover:text-text-primary'
            }`}
          >
            <Activity className="w-4 h-4" />
            <span>System Diagnostics (Infrastructure &amp; Health)</span>
            <span
              className={`w-2 h-2 rounded-full ${
                systemHealth?.status === 'healthy' ? 'bg-emerald-500' : 'bg-amber-500'
              }`}
            ></span>
          </button>
          <button
            onClick={() => setActiveTab('logins')}
            className={`py-3 border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === 'logins'
                ? 'border-accent-primary text-accent-primary font-semibold'
                : 'border-transparent text-text-secondary hover:text-text-primary'
            }`}
          >
            <LogIn className="w-4 h-4" />
            <span>Authentication Audits</span>
          </button>
        </div>
      </div>

      {/* Main Body */}
      <div className="max-w-7xl mx-auto w-full p-8 space-y-8 flex-1">
        {error && (
          <div className="p-4 rounded-xl border border-rose-300 dark:border-rose-900 bg-rose-50 dark:bg-rose-950/30 text-rose-800 dark:text-rose-200 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="font-semibold text-sm">Administrative Authorization Notice</h4>
              <p className="text-xs mt-0.5">{error}</p>
            </div>
          </div>
        )}

        {actionSuccessMessage && (
          <div className="p-4 rounded-xl border border-emerald-300 dark:border-emerald-900 bg-emerald-50 dark:bg-emerald-950/30 text-emerald-800 dark:text-emerald-200 flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>{actionSuccessMessage}</span>
            </div>
            <button onClick={() => setActionSuccessMessage(null)} className="p-1 hover:opacity-75">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Tab 1: Executive Overview */}
        {activeTab === 'overview' && (
          <div className="space-y-8">
            {/* 4 Core KPI Metric Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
              {/* Card 1: Users */}
              <div className="p-5 rounded-xl border border-border-primary bg-surface-secondary/30 shadow-sm space-y-2 hover:border-accent-primary/40 transition-colors">
                <div className="flex items-center justify-between text-text-secondary">
                  <span className="text-xs font-semibold uppercase tracking-wider">Registered Researchers</span>
                  <div className="p-2 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400">
                    <Users className="w-4 h-4" />
                  </div>
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-serif font-bold">{overview?.users.total_users || 0}</span>
                  <span className="text-xs text-emerald-600 font-medium">
                    +{overview?.users.new_users_today || 0} today
                  </span>
                </div>
                <div className="text-xs text-text-secondary pt-2 border-t border-border-primary flex items-center justify-between">
                  <span>Active 24h: <strong>{overview?.users.active_users_24h || 0}</strong></span>
                  <span>Active 7d: <strong>{overview?.users.active_users_7d || 0}</strong></span>
                </div>
              </div>

              {/* Card 2: Logins */}
              <div className="p-5 rounded-xl border border-border-primary bg-surface-secondary/30 shadow-sm space-y-2 hover:border-accent-primary/40 transition-colors">
                <div className="flex items-center justify-between text-text-secondary">
                  <span className="text-xs font-semibold uppercase tracking-wider">Authentication Events</span>
                  <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                    <LogIn className="w-4 h-4" />
                  </div>
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-serif font-bold">{overview?.logins.total_logins || 0}</span>
                  <span className="text-xs text-text-secondary">
                    {overview?.logins.logins_today || 0} today
                  </span>
                </div>
                <div className="text-xs text-text-secondary pt-2 border-t border-border-primary flex items-center justify-between">
                  <span>Failed total: <strong className="text-rose-500">{overview?.logins.failed_logins_total || 0}</strong></span>
                  <span>7d Unique: <strong>{overview?.logins.unique_users_logged_in_7d || 0}</strong></span>
                </div>
              </div>

              {/* Card 3: Storage */}
              <div className="p-5 rounded-xl border border-border-primary bg-surface-secondary/30 shadow-sm space-y-2 hover:border-accent-primary/40 transition-colors">
                <div className="flex items-center justify-between text-text-secondary">
                  <span className="text-xs font-semibold uppercase tracking-wider">Document Storage</span>
                  <div className="p-2 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400">
                    <HardDrive className="w-4 h-4" />
                  </div>
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-serif font-bold">{overview?.documents.total_storage_mb.toFixed(1) || 0}</span>
                  <span className="text-xs text-text-secondary">MB stored</span>
                </div>
                <div className="text-xs text-text-secondary pt-2 border-t border-border-primary flex items-center justify-between">
                  <span>Docs: <strong>{overview?.documents.total_documents || 0}</strong></span>
                  <span>Avg/User: <strong>{overview?.documents.average_storage_per_user_mb || 0} MB</strong></span>
                </div>
              </div>

              {/* Card 4: AI Operations */}
              <div className="p-5 rounded-xl border border-border-primary bg-surface-secondary/30 shadow-sm space-y-2 hover:border-accent-primary/40 transition-colors">
                <div className="flex items-center justify-between text-text-secondary">
                  <span className="text-xs font-semibold uppercase tracking-wider">Gemini AI Usage</span>
                  <div className="p-2 rounded-lg bg-purple-500/10 text-purple-600 dark:text-purple-400">
                    <Cpu className="w-4 h-4" />
                  </div>
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-serif font-bold">{overview?.ai_usage.total_requests || 0}</span>
                  <span className="text-xs text-text-secondary">
                    {(overview?.ai_usage.total_tokens || 0).toLocaleString()} toks
                  </span>
                </div>
                <div className="text-xs text-text-secondary pt-2 border-t border-border-primary flex items-center justify-between">
                  <span>Today: <strong>{overview?.ai_usage.requests_today || 0}</strong></span>
                  <span>Est. Cost: <strong>${(overview?.ai_usage.estimated_cost_usd || 0).toFixed(4)}</strong></span>
                </div>
              </div>
            </div>

            {/* Time Series Trend Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Chart 1: Registrations Trend */}
              <div className="p-6 rounded-xl border border-border-primary bg-surface-secondary/20 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-serif font-bold text-sm">Researcher Onboarding (Past 14 Days)</h3>
                    <p className="text-xs text-text-secondary">Daily user registrations</p>
                  </div>
                  <span className="text-xs font-semibold text-accent-primary">
                    +{overview?.users.new_users_this_week || 0} this week
                  </span>
                </div>

                <div className="h-44 flex items-end gap-2 pt-6 pb-2 border-b border-border-primary px-2">
                  {registrationSeries.map((pt) => {
                    const maxVal = Math.max(...registrationSeries.map((p) => p.count), 5);
                    const heightPercent = Math.max((pt.count / maxVal) * 100, 6);
                    return (
                      <div key={pt.date} className="flex-1 flex flex-col items-center gap-1.5 group relative">
                        {/* Tooltip */}
                        <div className="absolute -top-7 opacity-0 group-hover:opacity-100 transition-opacity bg-surface-tertiary border border-border-primary rounded px-1.5 py-0.5 text-[10px] whitespace-nowrap z-10 pointer-events-none">
                          {pt.date}: {pt.count}
                        </div>
                        <div
                          className="w-full bg-accent-primary/60 group-hover:bg-accent-primary rounded-t transition-all"
                          style={{ height: `${heightPercent}%` }}
                        ></div>
                        <span className="text-[9px] text-text-secondary rotate-45 origin-left truncate max-w-[28px]">
                          {pt.date.slice(5)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Chart 2: Login Activity Trend */}
              <div className="p-6 rounded-xl border border-border-primary bg-surface-secondary/20 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-serif font-bold text-sm">Authentication Volume & Health</h3>
                    <p className="text-xs text-text-secondary">Successful logins vs blocked/failed attempts</p>
                  </div>
                  <div className="flex items-center gap-3 text-xs">
                    <span className="flex items-center gap-1 text-emerald-600 font-medium">
                      <span className="w-2 h-2 rounded-full bg-emerald-500"></span> Success
                    </span>
                    <span className="flex items-center gap-1 text-rose-600 font-medium">
                      <span className="w-2 h-2 rounded-full bg-rose-500"></span> Failed
                    </span>
                  </div>
                </div>

                <div className="h-44 flex items-end gap-2 pt-6 pb-2 border-b border-border-primary px-2">
                  {loginSeries.map((pt) => {
                    const maxVal = Math.max(
                      ...loginSeries.map((p) => p.success_count + p.failure_count),
                      5
                    );
                    const sHeight = Math.max((pt.success_count / maxVal) * 100, 4);
                    const fHeight = (pt.failure_count / maxVal) * 100;
                    return (
                      <div key={pt.date} className="flex-1 flex flex-col items-center gap-1.5 group relative">
                        <div className="absolute -top-7 opacity-0 group-hover:opacity-100 transition-opacity bg-surface-tertiary border border-border-primary rounded px-1.5 py-0.5 text-[10px] whitespace-nowrap z-10 pointer-events-none">
                          {pt.date}: {pt.success_count} ok, {pt.failure_count} fail
                        </div>
                        <div className="w-full flex flex-col-reverse items-center h-full justify-start">
                          <div
                            className="w-full bg-emerald-500/70 group-hover:bg-emerald-500 rounded-t transition-all"
                            style={{ height: `${sHeight}%` }}
                          ></div>
                          {pt.failure_count > 0 && (
                            <div
                              className="w-full bg-rose-500 rounded-t transition-all"
                              style={{ height: `${fHeight}%` }}
                            ></div>
                          )}
                        </div>
                        <span className="text-[9px] text-text-secondary rotate-45 origin-left truncate max-w-[28px]">
                          {pt.date.slice(5)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* AI Models Breakdown & Storage Quota Health */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Models Breakdown */}
              <div className="p-6 rounded-xl border border-border-primary bg-surface-secondary/20 space-y-4">
                <h3 className="font-serif font-bold text-sm flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-purple-500" />
                  <span>Gemini Model Distribution</span>
                </h3>
                {overview?.ai_usage.models && overview.ai_usage.models.length > 0 ? (
                  <div className="divide-y divide-border-primary border border-border-primary rounded-lg overflow-hidden">
                    {overview.ai_usage.models.map((m) => (
                      <div key={m.model_name} className="p-3 flex items-center justify-between text-xs">
                        <div className="font-mono font-medium">{m.model_name}</div>
                        <div className="flex items-center gap-4 text-text-secondary">
                          <span>{m.request_count} requests</span>
                          <span className="font-semibold text-text-primary">
                            {m.total_tokens.toLocaleString()} tokens
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-text-secondary italic">No model interactions recorded yet.</p>
                )}
              </div>

              {/* Standard Storage Quota Compliance */}
              <div className="p-6 rounded-xl border border-border-primary bg-surface-secondary/20 space-y-4">
                <h3 className="font-serif font-bold text-sm flex items-center gap-2">
                  <HardDrive className="w-4 h-4 text-amber-500" />
                  <span>Storage Policy & Quota Compliance</span>
                </h3>
                <div className="p-4 rounded-lg border border-border-primary bg-surface-primary space-y-3">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-text-secondary">Standard Pilot Limit</span>
                    <span className="font-semibold">500 MB per Researcher</span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-text-secondary">Cumulative System Stored</span>
                    <span className="font-semibold">{overview?.documents.total_storage_mb.toFixed(2)} MB</span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-text-secondary">Failed Ingestions</span>
                    <span className="font-semibold text-rose-500">
                      {overview?.documents.failed_documents || 0}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Researchers Management */}
        {activeTab === 'researchers' && (
          <div className="space-y-6">
            {/* Search and Filters Bar */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 p-4 rounded-xl border border-border-primary bg-surface-secondary/30">
              <form onSubmit={handleSearchSubmit} className="relative flex-1 w-full">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search researchers by name or email..."
                  className="w-full pl-9 pr-4 py-2 rounded-lg border border-border-secondary bg-surface-primary text-text-primary text-xs focus:outline-none focus:border-accent-primary"
                />
              </form>

              <div className="flex items-center gap-3 w-full sm:w-auto">
                <select
                  value={statusFilter}
                  onChange={(e) => {
                    setStatusFilter(e.target.value);
                    setPage(1);
                  }}
                  className="px-3 py-2 rounded-lg border border-border-secondary bg-surface-primary text-text-primary text-xs focus:outline-none focus:border-accent-primary"
                >
                  <option value="">All Statuses</option>
                  <option value="active">Active</option>
                  <option value="suspended">Suspended</option>
                  <option value="inactive">Inactive</option>
                </select>

                <select
                  value={roleFilter}
                  onChange={(e) => {
                    setRoleFilter(e.target.value);
                    setPage(1);
                  }}
                  className="px-3 py-2 rounded-lg border border-border-secondary bg-surface-primary text-text-primary text-xs focus:outline-none focus:border-accent-primary"
                >
                  <option value="">All Roles</option>
                  <option value="admin">Administrators</option>
                  <option value="authenticated">Researchers</option>
                </select>
              </div>
            </div>

            {/* Researchers Table */}
            <div className="border border-border-primary rounded-xl overflow-hidden bg-surface-primary shadow-sm">
              <table className="w-full text-left text-xs">
                <thead className="bg-surface-secondary/50 border-b border-border-primary text-text-secondary font-semibold">
                  <tr>
                    <th className="py-3 px-4">Researcher</th>
                    <th className="py-3 px-4">Role</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Storage (500 MB Quota)</th>
                    <th className="py-3 px-4">AI Queries</th>
                    <th className="py-3 px-4">Logins</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-primary">
                  {tableLoading ? (
                    <tr>
                      <td colSpan={7} className="py-12 text-center text-text-secondary">
                        <div className="w-6 h-6 border-2 border-accent-primary border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
                        <p>Filtering researchers...</p>
                      </td>
                    </tr>
                  ) : usersList.length > 0 ? (
                    usersList.map((u) => {
                      const quotaPct = Math.min(
                        Math.round(((u.storage_used_mb || 0) / (u.storage_quota_mb || 500)) * 100),
                        100
                      );
                      return (
                        <tr
                          key={u.id}
                          onClick={() => setSelectedUser(u)}
                          className="hover:bg-surface-secondary/30 cursor-pointer transition-colors"
                        >
                          <td className="py-3 px-4">
                            <div className="flex items-center gap-2.5">
                              <div className="w-8 h-8 rounded-full bg-accent-primary/10 border border-accent-primary/20 flex items-center justify-center text-accent-primary font-serif font-bold text-xs flex-shrink-0">
                                {u.display_name?.charAt(0).toUpperCase() || u.email.charAt(0).toUpperCase()}
                              </div>
                              <div>
                                <div className="font-semibold text-text-primary">{u.display_name}</div>
                                <div className="text-[11px] text-text-secondary">{u.email}</div>
                              </div>
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                                u.role === 'admin'
                                  ? 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300 dark:border-amber-700'
                                  : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-700'
                              }`}
                            >
                              {u.role === 'admin' ? 'Admin' : 'Researcher'}
                            </span>
                          </td>
                          <td className="py-3 px-4">
                            <div className="flex flex-col gap-1">
                              <span
                                className={`px-2 py-0.5 rounded-full text-[10px] font-medium w-fit ${
                                  u.is_active
                                    ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400'
                                    : 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400'
                                }`}
                              >
                                {u.status}
                              </span>
                              {u.access_status && (
                                <span
                                  className={`px-2 py-0.5 rounded-full text-[9px] font-semibold tracking-wide uppercase w-fit ${
                                    u.access_status === 'active'
                                      ? 'bg-teal-500/10 text-teal-700 dark:text-teal-300 border border-teal-500/20'
                                      : u.access_status === 'revoked'
                                      ? 'bg-rose-500/10 text-rose-700 dark:text-rose-300 border border-rose-500/20'
                                      : u.access_status === 'approved_invitation_pending'
                                      ? 'bg-blue-500/10 text-blue-700 dark:text-blue-300 border border-blue-500/20'
                                      : 'bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/20'
                                  }`}
                                >
                                  {u.access_status.replace(/_/g, ' ')}
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            <div className="space-y-1 max-w-[140px]">
                              <div className="flex items-center justify-between text-[11px]">
                                <span>{u.storage_used_mb.toFixed(1)} MB</span>
                                <span className="text-text-secondary">{quotaPct}%</span>
                              </div>
                              <div className="w-full h-1.5 bg-surface-tertiary rounded-full overflow-hidden border border-border-secondary">
                                <div
                                  className={`h-full ${
                                    quotaPct >= 90
                                      ? 'bg-rose-500'
                                      : quotaPct >= 75
                                      ? 'bg-amber-500'
                                      : 'bg-emerald-500'
                                  }`}
                                  style={{ width: `${quotaPct}%` }}
                                ></div>
                              </div>
                            </div>
                          </td>
                          <td className="py-3 px-4 text-text-secondary">
                            <div><strong>{u.ai_request_count}</strong> calls</div>
                            <div className="text-[10px]">{u.ai_total_tokens.toLocaleString()} toks</div>
                          </td>
                          <td className="py-3 px-4 text-text-secondary">
                            <div><strong>{u.login_count}</strong> logins</div>
                            <div className="text-[10px]">
                              {u.last_login_at
                                ? new Date(u.last_login_at).toLocaleDateString()
                                : 'Never'}
                            </div>
                          </td>
                          <td className="py-3 px-4 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setSelectedUser(u);
                                }}
                                className="px-2.5 py-1 rounded border border-border-secondary bg-surface-secondary/40 hover:bg-surface-secondary text-text-primary text-[11px] font-medium transition-colors"
                              >
                                Inspect
                              </button>
                              {u.role !== 'admin' && u.access_status === 'active' && (
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleRevokeUser(u.id, u.email);
                                  }}
                                  className="px-2 py-1 rounded border border-rose-300 dark:border-rose-900 bg-rose-50 hover:bg-rose-100 dark:bg-rose-950/30 text-rose-700 dark:text-rose-300 text-[11px] font-medium transition-colors"
                                  title="Revoke research access immediately"
                                >
                                  Revoke
                                </button>
                              )}
                              {u.role !== 'admin' && u.access_status === 'revoked' && (
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleReactivateUser(u.id, u.email);
                                  }}
                                  className="px-2 py-1 rounded border border-emerald-300 dark:border-emerald-900 bg-emerald-50 hover:bg-emerald-100 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300 text-[11px] font-medium transition-colors"
                                  title="Reactivate research access"
                                >
                                  Reactivate
                                </button>
                              )}
                              {u.role !== 'admin' && (u.access_status === 'pending_request' || u.access_status === 'request_submitted') && (
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDirectActivateUser(u.id, u.email);
                                  }}
                                  className="px-2 py-1 rounded border border-teal-300 dark:border-teal-900 bg-teal-50 hover:bg-teal-100 dark:bg-teal-950/30 text-teal-700 dark:text-teal-300 text-[11px] font-medium transition-colors"
                                  title="Direct activate researcher without invitation token"
                                >
                                  Activate
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={7} className="py-12 text-center text-text-secondary italic">
                        No registered researchers matched the query.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>

              {/* Pagination Bar */}
              <div className="p-3 border-t border-border-primary bg-surface-secondary/20 flex items-center justify-between text-xs text-text-secondary">
                <span>
                  Showing {usersList.length} of {usersTotal} researchers
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(p - 1, 1))}
                    disabled={page <= 1}
                    className="p-1 rounded border border-border-secondary hover:bg-surface-tertiary disabled:opacity-40"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span>
                    Page {page} of {totalPages}
                  </span>
                  <button
                    onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
                    disabled={page >= totalPages}
                    className="p-1 rounded border border-border-secondary hover:bg-surface-tertiary disabled:opacity-40"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab: Access Requests & Cryptographic Invitations */}
        {activeTab === 'access_requests' && (
          <div className="space-y-8">
            {/* Header / Actions Bar */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-5 rounded-xl border border-border-primary bg-surface-secondary/30">
              <div>
                <h3 className="text-base font-serif font-bold text-text-primary flex items-center gap-2">
                  <UserCheck className="w-5 h-5 text-accent-primary" />
                  <span>Research Access Requests &amp; Cryptographic Invitations</span>
                </h3>
                <p className="text-xs text-text-secondary mt-1 max-w-2xl">
                  Review researcher applications, approve requests to generate cryptographically bound 256-bit entropy tokens, or directly issue invitations.
                </p>
              </div>
              <button
                onClick={() => setDirectInvModalOpen(true)}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-accent-primary text-white text-xs font-semibold hover:opacity-90 transition-opacity shadow-sm shrink-0"
              >
                <Plus className="w-4 h-4" />
                <span>Direct-Issue Invitation</span>
              </button>
            </div>

            {/* SECTION 1: Access Requests */}
            <div className="space-y-4">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div className="flex items-center gap-2">
                  <h4 className="font-serif font-bold text-sm text-text-primary">
                    Access Applications ({accessRequests.length})
                  </h4>
                  <span className="text-xs text-text-secondary">
                    ({accessRequests.filter((r) => r.status === 'pending').length} pending review)
                  </span>
                </div>

                {/* Filter Pills */}
                <div className="flex items-center gap-1 p-1 rounded-lg border border-border-primary bg-surface-secondary/40 text-xs">
                  {(['all', 'pending', 'approved', 'rejected'] as const).map((st) => (
                    <button
                      key={st}
                      onClick={() => setRequestFilter(st)}
                      className={`px-3 py-1 rounded-md capitalize font-medium transition-colors ${
                        requestFilter === st
                          ? 'bg-accent-primary text-white shadow-xs'
                          : 'text-text-secondary hover:text-text-primary'
                      }`}
                    >
                      {st}
                    </button>
                  ))}
                </div>
              </div>

              {/* Access Requests Table */}
              <div className="border border-border-primary rounded-xl overflow-hidden bg-surface-primary shadow-sm">
                <table className="w-full text-left text-xs">
                  <thead className="bg-surface-secondary/50 border-b border-border-primary text-text-secondary font-semibold">
                    <tr>
                      <th className="py-3 px-4">Researcher</th>
                      <th className="py-3 px-4">Submitted</th>
                      <th className="py-3 px-4">Stated Purpose of Use</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border-primary">
                    {accessRequestsLoading ? (
                      <tr>
                        <td colSpan={5} className="py-10 text-center text-text-secondary">
                          <div className="w-5 h-5 border-2 border-accent-primary border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
                          <span>Loading access requests...</span>
                        </td>
                      </tr>
                    ) : accessRequests.filter((r) => (requestFilter === 'all' ? true : r.status === requestFilter)).length > 0 ? (
                      accessRequests
                        .filter((r) => (requestFilter === 'all' ? true : r.status === requestFilter))
                        .map((req) => (
                          <tr key={req.id} className="hover:bg-surface-secondary/20 transition-colors">
                            <td className="py-3 px-4">
                              <div className="font-semibold text-text-primary">
                                {req.user_display_name || 'Registered User'}
                              </div>
                              <div className="text-[11px] text-text-secondary">{req.user_email}</div>
                              {req.institution && (
                                <div className="text-[10px] text-accent-primary font-medium mt-0.5">
                                  {req.institution}
                                </div>
                              )}
                            </td>
                            <td className="py-3 px-4 text-text-secondary whitespace-nowrap">
                              <div>{new Date(req.created_at).toLocaleDateString()}</div>
                              <div className="text-[10px]">{new Date(req.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                            </td>
                            <td className="py-3 px-4 max-w-md">
                              <p className="text-text-primary text-[11px] leading-relaxed line-clamp-3">
                                {req.research_purpose}
                              </p>
                              {req.rejection_reason && req.status === 'rejected' && (
                                <div className="mt-1.5 p-2 rounded bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-200 text-[10px]">
                                  <strong>Rejection Reason:</strong> {req.rejection_reason}
                                </div>
                              )}
                            </td>
                            <td className="py-3 px-4 whitespace-nowrap">
                              <span
                                className={`px-2 py-0.5 rounded-full text-[10px] font-semibold tracking-wide uppercase ${
                                  req.status === 'approved'
                                    ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-700'
                                    : req.status === 'rejected'
                                    ? 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-300 dark:border-rose-700'
                                    : 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300 dark:border-amber-700'
                                }`}
                              >
                                {req.status}
                              </span>
                            </td>
                            <td className="py-3 px-4 text-right whitespace-nowrap">
                              {req.status === 'pending' ? (
                                <div className="flex items-center justify-end gap-1.5">
                                  <button
                                    onClick={() => handleApproveRequest(req)}
                                    disabled={actionLoading}
                                    className="px-3 py-1 rounded bg-emerald-600 hover:bg-emerald-700 text-white text-[11px] font-semibold flex items-center gap-1 transition-colors disabled:opacity-50"
                                  >
                                    <Check className="w-3.5 h-3.5" />
                                    <span>Approve</span>
                                  </button>
                                  <button
                                    onClick={() => {
                                      setRejectModalReq(req);
                                      setRejectReason('');
                                    }}
                                    disabled={actionLoading}
                                    className="px-2.5 py-1 rounded border border-rose-300 dark:border-rose-800 bg-rose-50 hover:bg-rose-100 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 text-[11px] font-medium transition-colors"
                                  >
                                    <X className="w-3.5 h-3.5" />
                                    <span>Reject</span>
                                  </button>
                                </div>
                              ) : (
                                <span className="text-[11px] text-text-secondary">
                                  Reviewed {req.reviewed_at ? new Date(req.reviewed_at).toLocaleDateString() : 'Completed'}
                                </span>
                              )}
                            </td>
                          </tr>
                        ))
                    ) : (
                      <tr>
                        <td colSpan={5} className="py-10 text-center text-text-secondary italic">
                          No access requests matched the selected filter.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* SECTION 2: Cryptographic Invitations */}
            <div className="space-y-4 pt-4 border-t border-border-primary">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-serif font-bold text-sm text-text-primary flex items-center gap-2">
                    <Key className="w-4 h-4 text-amber-500" />
                    <span>Cryptographic Invitations ({invitations.length})</span>
                  </h4>
                  <p className="text-xs text-text-secondary mt-0.5">
                    Security Architecture: Tokens contain 256 bits of CSPRNG entropy. The database stores only salted SHA-256 hashes.
                  </p>
                </div>
              </div>

              <div className="border border-border-primary rounded-xl overflow-hidden bg-surface-primary shadow-sm">
                <table className="w-full text-left text-xs">
                  <thead className="bg-surface-secondary/50 border-b border-border-primary text-text-secondary font-semibold">
                    <tr>
                      <th className="py-3 px-4">Researcher Email</th>
                      <th className="py-3 px-4">Created</th>
                      <th className="py-3 px-4">Expires</th>
                      <th className="py-3 px-4">Token Status</th>
                      <th className="py-3 px-4">Redemption Details</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border-primary">
                    {invitationsLoading ? (
                      <tr>
                        <td colSpan={6} className="py-10 text-center text-text-secondary">
                          <div className="w-5 h-5 border-2 border-accent-primary border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
                          <span>Loading invitations...</span>
                        </td>
                      </tr>
                    ) : invitations.length > 0 ? (
                      invitations.map((inv) => {
                        const isExpired = new Date(inv.expires_at) < new Date();
                        const isRedeemed = inv.is_redeemed;
                        return (
                          <tr key={inv.id} className="hover:bg-surface-secondary/20 transition-colors">
                            <td className="py-3 px-4 font-medium text-text-primary">
                              {inv.user_email || 'Associated Researcher'}
                            </td>
                            <td className="py-3 px-4 text-text-secondary">
                              {new Date(inv.created_at).toLocaleDateString()}
                            </td>
                            <td className="py-3 px-4 text-text-secondary">
                              {new Date(inv.expires_at).toLocaleDateString()}
                            </td>
                            <td className="py-3 px-4">
                              <span
                                className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide ${
                                  isRedeemed
                                    ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-700'
                                    : isExpired
                                    ? 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300 border border-gray-300 dark:border-gray-700'
                                    : 'bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300 border border-blue-300 dark:border-blue-700'
                                }`}
                              >
                                {isRedeemed ? 'Redeemed' : isExpired ? 'Expired' : 'Active'}
                              </span>
                            </td>
                            <td className="py-3 px-4 text-text-secondary">
                              {isRedeemed && inv.redeemed_at
                                ? `Redeemed ${new Date(inv.redeemed_at).toLocaleString()}`
                                : isExpired
                                ? 'Expired unredeemed'
                                : 'Pending researcher redemption'}
                            </td>
                            <td className="py-3 px-4 text-right">
                              {!isRedeemed && (
                                <button
                                  onClick={() => handleDeleteInvitation(inv.id)}
                                  className="px-2.5 py-1 rounded border border-rose-300 dark:border-rose-900 bg-rose-50 hover:bg-rose-100 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 text-[11px] font-medium transition-colors inline-flex items-center gap-1"
                                  title="Revoke / Cancel this invitation"
                                >
                                  <Trash2 className="w-3 h-3" />
                                  <span>Revoke</span>
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td colSpan={6} className="py-10 text-center text-text-secondary italic">
                          No invitations issued yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: System Diagnostics & Health */}
        {activeTab === 'health' && (
          <AdminSystemDiagnosticsView />
        )}

        {/* Tab 4: Authentication Audits */}
        {activeTab === 'logins' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-serif font-bold text-base">Authentication Security Stream</h3>
                <p className="text-xs text-text-secondary">
                  Audited login attempts, IP origins, and failed password challenge events across all researchers.
                </p>
              </div>
              <span className="text-xs text-text-secondary">
                Total Logins Audited: {overview?.logins.total_logins || 0}
              </span>
            </div>

            <div className="p-4 rounded-xl border border-border-primary bg-surface-secondary/30 space-y-2 text-xs">
              <div className="flex items-center gap-2 font-medium">
                <Lock className="w-4 h-4 text-accent-primary" />
                <span>Zero Secrets Principle</span>
              </div>
              <p className="text-text-secondary">
                ORION never records plaintext passwords, hashed credentials, or session tokens in audit event logs. Only sanitized metadata (event type, outcome, masked client IP, user agent, and failure codes) is retained.
              </p>
            </div>

            <div className="p-8 text-center border border-border-primary rounded-xl bg-surface-secondary/10 space-y-3">
              <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto" />
              <h4 className="font-serif font-bold text-sm">Security Audit Active</h4>
              <p className="text-xs text-text-secondary max-w-md mx-auto">
                Individual researcher login events and failed attempts can also be inspected directly from the Researcher Directory by selecting any user profile.
              </p>
              <button
                onClick={() => setActiveTab('researchers')}
                className="px-4 py-1.5 rounded-lg border border-border-secondary bg-surface-primary hover:bg-surface-tertiary text-xs font-medium transition-colors"
              >
                Go to Researcher Directory
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Selected Researcher Modal */}
      {selectedUser && (
        <AdminUserDetailModal user={selectedUser} onClose={() => setSelectedUser(null)} />
      )}

      {/* One-Time Token Modal */}
      {oneTimeTokenData && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm"
        >
          <div className="w-full max-w-lg bg-surface-primary rounded-xl border border-border-primary shadow-2xl p-6 space-y-5">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                  <Key className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-serif font-bold text-lg text-text-primary">Cryptographic Invitation Generated</h3>
                  <p className="text-xs text-text-secondary">Bound exclusively to {oneTimeTokenData.email}</p>
                </div>
              </div>
              <button
                onClick={() => setOneTimeTokenData(null)}
                className="p-1.5 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-secondary"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Warning Banner */}
            <div className="p-3.5 rounded-lg border border-amber-300 dark:border-amber-700/60 bg-amber-50 dark:bg-amber-950/30 text-amber-900 dark:text-amber-200 text-xs flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5 text-amber-600 dark:text-amber-400" />
              <div>
                <strong className="font-semibold">One-Time Display Warning:</strong>
                <p className="mt-0.5 leading-relaxed">
                  This plaintext token will <strong>NEVER</strong> be displayed again. ORION stores only a salted SHA-256 hash. Copy this token or the direct redemption link and securely deliver it to the researcher.
                </p>
              </div>
            </div>

            {/* Token display */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-text-secondary">Invitation Token</label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  readOnly
                  value={oneTimeTokenData.token}
                  className="flex-1 px-3 py-2 rounded-lg border border-border-secondary bg-surface-secondary/50 font-mono text-xs text-text-primary select-all"
                />
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(oneTimeTokenData.token);
                    setTokenCopied(true);
                    setTimeout(() => setTokenCopied(false), 2500);
                  }}
                  className="px-3 py-2 rounded-lg border border-accent-primary bg-accent-primary text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm hover:opacity-90 transition-opacity"
                >
                  {tokenCopied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{tokenCopied ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
            </div>

            {/* Direct redemption link */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-text-secondary">Direct Redemption URL</label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  readOnly
                  value={`${window.location.origin}/redeem?token=${encodeURIComponent(oneTimeTokenData.token)}`}
                  className="flex-1 px-3 py-2 rounded-lg border border-border-secondary bg-surface-secondary/50 font-mono text-xs text-text-primary truncate select-all"
                />
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(
                      `${window.location.origin}/redeem?token=${encodeURIComponent(oneTimeTokenData.token)}`
                    );
                    setLinkCopied(true);
                    setTimeout(() => setLinkCopied(false), 2500);
                  }}
                  className="px-3 py-2 rounded-lg border border-border-secondary bg-surface-secondary hover:bg-surface-tertiary text-text-primary text-xs font-medium flex items-center gap-1.5 transition-colors"
                >
                  {linkCopied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{linkCopied ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
              <p className="text-[11px] text-text-secondary">
                Expires on: {new Date(oneTimeTokenData.expiresAt).toLocaleString()}
              </p>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={() => setOneTimeTokenData(null)}
                className="px-4 py-2 rounded-lg border border-border-secondary bg-surface-secondary hover:bg-surface-tertiary text-text-primary text-xs font-medium transition-colors"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reject Request Modal */}
      {rejectModalReq && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm"
        >
          <div className="w-full max-w-md bg-surface-primary rounded-xl border border-border-primary shadow-2xl p-6 space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-serif font-bold text-base text-text-primary">Reject Research Access Request</h3>
                <p className="text-xs text-text-secondary mt-0.5">
                  Researcher: {rejectModalReq.user_display_name || rejectModalReq.user_email}
                </p>
              </div>
              <button
                onClick={() => {
                  setRejectModalReq(null);
                  setRejectReason('');
                }}
                className="p-1 rounded text-text-secondary hover:text-text-primary hover:bg-surface-secondary"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-text-secondary">
                Reason for Rejection <span className="text-rose-500">*</span>
              </label>
              <textarea
                rows={3}
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="State why this request is not approved (e.g. Scope outside EPR academic pilot, unverified institutional affiliation)..."
                className="w-full px-3 py-2 rounded-lg border border-border-secondary bg-surface-secondary/40 text-text-primary text-xs focus:outline-none focus:border-accent-primary"
              />
              <p className="text-[11px] text-text-secondary">
                This explanation will be visible to the researcher on their Access Pending screen.
              </p>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => {
                  setRejectModalReq(null);
                  setRejectReason('');
                }}
                className="px-3.5 py-1.5 rounded-lg border border-border-secondary bg-surface-secondary hover:bg-surface-tertiary text-xs font-medium transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmReject}
                disabled={!rejectReason.trim() || actionLoading}
                className="px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold transition-colors disabled:opacity-50"
              >
                {actionLoading ? 'Rejecting...' : 'Confirm Rejection'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Direct-Issue Invitation Modal */}
      {directInvModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm"
        >
          <div className="w-full max-w-md bg-surface-primary rounded-xl border border-border-primary shadow-2xl p-6 space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-serif font-bold text-base text-text-primary">Direct-Issue Researcher Invitation</h3>
                <p className="text-xs text-text-secondary mt-0.5">
                  Generate an invitation token directly for a registered account.
                </p>
              </div>
              <button
                onClick={() => setDirectInvModalOpen(false)}
                className="p-1 rounded text-text-secondary hover:text-text-primary hover:bg-surface-secondary"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleDirectCreateInvitation} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-text-secondary">Select Researcher Account</label>
                <select
                  value={directInvUserId}
                  onChange={(e) => setDirectInvUserId(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-border-secondary bg-surface-secondary/40 text-text-primary text-xs focus:outline-none focus:border-accent-primary"
                  required
                >
                  <option value="">-- Choose registered account --</option>
                  {usersList.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.display_name} ({u.email}) — [{u.access_status || u.status}]
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-text-secondary">Token Validity Period</label>
                <select
                  value={directInvDays}
                  onChange={(e) => setDirectInvDays(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg border border-border-secondary bg-surface-secondary/40 text-text-primary text-xs focus:outline-none focus:border-accent-primary"
                >
                  <option value={1}>1 Day (Urgent)</option>
                  <option value={3}>3 Days</option>
                  <option value={7}>7 Days (Standard default)</option>
                  <option value={14}>14 Days</option>
                  <option value={30}>30 Days (Extended)</option>
                </select>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setDirectInvModalOpen(false)}
                  className="px-3.5 py-1.5 rounded-lg border border-border-secondary bg-surface-secondary hover:bg-surface-tertiary text-xs font-medium transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!directInvUserId || actionLoading}
                  className="px-3.5 py-1.5 rounded-lg bg-accent-primary hover:opacity-90 text-white text-xs font-semibold transition-opacity disabled:opacity-50"
                >
                  {actionLoading ? 'Generating...' : 'Generate Token'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

