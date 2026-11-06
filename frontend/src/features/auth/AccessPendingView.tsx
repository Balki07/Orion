import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  Clock,
  CheckCircle2,
  XCircle,
  KeyRound,
  Send,
  LogOut,
  Building,
  FileText,
  AlertCircle,
  Sparkles,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { OrionLogo } from '../../components/icons/OrionLogo';
import { ThemeToggle } from '../../components/ui/ThemeToggle';
import { toast } from 'sonner';

export const AccessPendingView: React.FC = () => {
  const { user, signOut, checkSession } = useAuth();
  const [institution, setInstitution] = useState<string>(user?.institution || '');
  const [researchPurpose, setResearchPurpose] = useState<string>('');
  const [intendedDataTypes, setIntendedDataTypes] = useState<string>('academic_papers');
  const [invitationToken, setInvitationToken] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isRedeeming, setIsRedeeming] = useState<boolean>(false);
  const [existingRequest, setExistingRequest] = useState<any>(null);
  const [isLoadingRequest, setIsLoadingRequest] = useState<boolean>(true);
  const [showRedeemCard, setShowRedeemCard] = useState<boolean>(
    user?.access_status === 'approved_invitation_pending'
  );

  useEffect(() => {
    loadRequest();
  }, []);

  const loadRequest = async () => {
    try {
      setIsLoadingRequest(true);
      const req = await api.getOwnAccessRequest();
      setExistingRequest(req);
      if (req?.institution && !institution) {
        setInstitution(req.institution);
      }
    } catch (err) {
      console.error('Failed to load own access request:', err);
    } finally {
      setIsLoadingRequest(false);
    }
  };

  const handleSubmitRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (researchPurpose.trim().length < 10) {
      toast.error('Research purpose must be at least 10 characters long.');
      return;
    }

    try {
      setIsSubmitting(true);
      const res = await api.submitAccessRequest({
        institution: institution.trim() || undefined,
        research_purpose: researchPurpose.trim(),
        intended_data_types: intendedDataTypes || undefined,
      });
      toast.success('Research access request submitted successfully.');
      setExistingRequest(res);
      await checkSession?.();
    } catch (err: any) {
      toast.error(err.detail || err.message || 'Failed to submit access request.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRedeemInvitation = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = invitationToken.trim();
    if (!token) {
      toast.error('Please enter your invitation token.');
      return;
    }

    try {
      setIsRedeeming(true);
      const res = await api.redeemInvitation(token);
      toast.success(res.message || 'Invitation redeemed! Your workspace is activated.');
      await checkSession?.();
      window.location.reload();
    } catch (err: any) {
      toast.error(err.detail || err.message || 'Invalid or expired invitation token.');
    } finally {
      setIsRedeeming(false);
    }
  };

  const accessStatus = user?.access_status || 'pending_request';

  return (
    <div className="min-h-screen w-screen flex flex-col bg-[#FAF8F5] dark:bg-[#0c0d12] text-[#1E293B] dark:text-[#E2E8F0] font-sans transition-colors">
      {/* Top Navigation Bar */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-[#E2E8F0] dark:border-[#1E293B] bg-white/70 dark:bg-[#12141C]/70 backdrop-blur-md sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <OrionLogo size={28} showWordmark={true} />
          <span className="hidden sm:inline-block text-[11px] font-mono tracking-wider px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20 uppercase font-medium">
            Private Access Control
          </span>
        </div>

        <div className="flex items-center gap-3">
          <ThemeToggle />
          <div className="hidden sm:flex flex-col text-right">
            <span className="text-xs font-semibold text-ink-900 dark:text-ink-100">
              {user?.display_name || user?.email}
            </span>
            <span className="text-[11px] text-ink-500 font-mono">
              Status: <span className="font-semibold capitalize text-amber-600 dark:text-amber-400">{accessStatus.replace('_', ' ')}</span>
            </span>
          </div>
          <button
            onClick={() => signOut()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-rose-700 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 border border-rose-200 dark:border-rose-900/40 transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign Out</span>
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 flex items-center justify-center p-4 sm:p-6 md:p-10">
        <div className="w-full max-w-2xl bg-white dark:bg-[#141722] rounded-2xl border border-[#E2E8F0] dark:border-[#1E293B] shadow-xl p-6 sm:p-8 md:p-10">
          {/* Header Banner */}
          <div className="text-center mb-8">
            <div className="inline-flex p-3 rounded-2xl bg-blue-50 dark:bg-blue-950/40 border border-blue-100 dark:border-blue-900/40 text-blue-700 dark:text-blue-400 mb-4 shadow-xs">
              {accessStatus === 'request_submitted' && <Clock className="w-7 h-7 text-amber-600 animate-pulse" />}
              {accessStatus === 'approved_invitation_pending' && <Sparkles className="w-7 h-7 text-emerald-600" />}
              {accessStatus === 'rejected' && <XCircle className="w-7 h-7 text-rose-600" />}
              {accessStatus === 'revoked' && <ShieldAlert className="w-7 h-7 text-rose-600" />}
              {accessStatus === 'pending_request' && <Building className="w-7 h-7 text-blue-600" />}
            </div>

            <h1 className="text-2xl sm:text-3xl font-serif font-bold text-ink-950 dark:text-white tracking-tight">
              {accessStatus === 'request_submitted' && 'Research Access Under Review'}
              {accessStatus === 'approved_invitation_pending' && 'Access Approved — Invitation Required'}
              {accessStatus === 'rejected' && 'Research Access Request Declined'}
              {accessStatus === 'revoked' && 'Research Workspace Access Revoked'}
              {accessStatus === 'pending_request' && 'Request Research Platform Access'}
            </h1>

            <p className="mt-2 text-xs sm:text-sm text-ink-600 dark:text-ink-300 max-w-lg mx-auto leading-relaxed">
              ORION is a private, evidence-grounded academic research platform. To protect scholarly data integrity and model quotas, access to the research workspace is granted by administrator review.
            </p>
          </div>

          {/* Account Profile Pill */}
          <div className="mb-6 p-4 rounded-xl bg-[#FAF8F5] dark:bg-[#0c0d12] border border-[#E2E8F0] dark:border-[#1E293B] flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
            <div>
              <span className="text-[11px] font-mono text-ink-500 uppercase tracking-wider block">Authenticated Account</span>
              <span className="font-semibold text-ink-900 dark:text-ink-100">{user?.email}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono text-ink-500 uppercase tracking-wider">Access State:</span>
              <span className="px-2.5 py-1 rounded-full text-[11px] font-mono font-medium capitalize bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/30">
                {accessStatus.replace('_', ' ')}
              </span>
            </div>
          </div>

          {/* State-Specific Body */}
          {accessStatus === 'request_submitted' && (
            <div className="space-y-6">
              <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/40">
                <div className="flex items-start gap-3">
                  <Clock className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
                  <div className="text-xs space-y-1">
                    <p className="font-semibold text-amber-900 dark:text-amber-300">
                      Your access application has been received
                    </p>
                    <p className="text-amber-800 dark:text-amber-400/90 leading-relaxed">
                      An administrator is reviewing your research proposal. Once approved, you will receive a cryptographic invitation token to activate your workspace.
                    </p>
                    {existingRequest?.created_at && (
                      <p className="text-[11px] text-amber-700 dark:text-amber-500 font-mono mt-2">
                        Submitted: {new Date(existingRequest.created_at).toLocaleString()}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {existingRequest?.research_purpose && (
                <div className="p-4 rounded-xl bg-[#FAF8F5] dark:bg-[#0c0d12] border border-[#E2E8F0] dark:border-[#1E293B] text-xs">
                  <span className="text-[11px] font-mono uppercase text-ink-500 block mb-1">Stated Research Purpose:</span>
                  <p className="text-ink-800 dark:text-ink-200 italic leading-relaxed">
                    "{existingRequest.research_purpose}"
                  </p>
                  {existingRequest.institution && (
                    <p className="text-[11px] text-ink-500 font-mono mt-2">
                      Affiliation: {existingRequest.institution}
                    </p>
                  )}
                </div>
              )}
            </div>
          )}

          {accessStatus === 'approved_invitation_pending' && (
            <div className="space-y-6">
              <div className="p-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-900/40">
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 mt-0.5 shrink-0" />
                  <div className="text-xs space-y-1">
                    <p className="font-semibold text-emerald-900 dark:text-emerald-300">
                      Congratulations! Your access request was approved
                    </p>
                    <p className="text-emerald-800 dark:text-emerald-400/90 leading-relaxed">
                      Please enter the one-time cryptographic invitation token provided by your platform administrator to activate your research workspace.
                    </p>
                  </div>
                </div>
              </div>

              <form onSubmit={handleRedeemInvitation} className="space-y-4">
                <div>
                  <label htmlFor="invitationToken" className="block text-xs font-semibold text-ink-800 dark:text-ink-200 mb-1.5">
                    Invitation Token
                  </label>
                  <div className="relative">
                    <KeyRound className="w-4 h-4 absolute left-3 top-3 text-ink-400" />
                    <input
                      id="invitationToken"
                      type="text"
                      required
                      value={invitationToken}
                      onChange={(e) => setInvitationToken(e.target.value)}
                      placeholder="Paste your invitation token here..."
                      className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-[#CBD5E1] dark:border-[#334155] bg-white dark:bg-[#0c0d12] text-ink-950 dark:text-white placeholder-ink-400 focus:outline-hidden focus:ring-2 focus:ring-navy-600 font-mono"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={isRedeeming}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold shadow-subtle transition-all disabled:opacity-50"
                >
                  {isRedeeming ? (
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      <span>Activate Research Workspace</span>
                    </>
                  )}
                </button>
              </form>
            </div>
          )}

          {accessStatus === 'rejected' && (
            <div className="space-y-6">
              <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/40">
                <div className="flex items-start gap-3">
                  <XCircle className="w-5 h-5 text-rose-600 mt-0.5 shrink-0" />
                  <div className="text-xs space-y-1">
                    <p className="font-semibold text-rose-900 dark:text-rose-300">
                      Application Declined
                    </p>
                    <p className="text-rose-800 dark:text-rose-400/90 leading-relaxed">
                      {existingRequest?.rejection_reason || 'Your access application was declined by the platform administrator.'}
                    </p>
                  </div>
                </div>
              </div>

              <div className="text-center">
                <p className="text-xs text-ink-600 dark:text-ink-400 mb-4">
                  You may submit an updated application with additional institutional context.
                </p>
                <button
                  type="button"
                  onClick={() => setExistingRequest(null)}
                  className="px-4 py-2 rounded-lg bg-navy-800 text-white text-xs font-semibold hover:bg-navy-900 transition-colors"
                >
                  Re-Apply with Updated Details
                </button>
              </div>
            </div>
          )}

          {accessStatus === 'revoked' && (
            <div className="space-y-6">
              <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/40">
                <div className="flex items-start gap-3">
                  <ShieldAlert className="w-5 h-5 text-rose-600 mt-0.5 shrink-0" />
                  <div className="text-xs space-y-1">
                    <p className="font-semibold text-rose-900 dark:text-rose-300">
                      Access Revoked
                    </p>
                    <p className="text-rose-800 dark:text-rose-400/90 leading-relaxed">
                      Research workspace access has been revoked for this account by an administrator. Please reach out to your organizational lead for assistance.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {(accessStatus === 'pending_request' || (accessStatus === 'rejected' && !existingRequest)) && (
            <form onSubmit={handleSubmitRequest} className="space-y-4">
              <div>
                <label htmlFor="userEmail" className="block text-xs font-semibold text-ink-800 dark:text-ink-200 mb-1">
                  Registered Research Email (Read-Only)
                </label>
                <input
                  id="userEmail"
                  type="email"
                  disabled
                  value={user?.email || ''}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-[#CBD5E1] dark:border-[#334155] bg-gray-100 dark:bg-[#0c0d12]/50 text-ink-500 cursor-not-allowed font-mono"
                />
              </div>

              <div>
                <label htmlFor="institution" className="block text-xs font-semibold text-ink-800 dark:text-ink-200 mb-1">
                  Academic or Institutional Affiliation (Optional)
                </label>
                <div className="relative">
                  <Building className="w-4 h-4 absolute left-3 top-2.5 text-ink-400" />
                  <input
                    id="institution"
                    type="text"
                    value={institution}
                    onChange={(e) => setInstitution(e.target.value)}
                    placeholder="e.g. Stanford University, Max Planck Institute, Ellen MacArthur Foundation"
                    className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-[#CBD5E1] dark:border-[#334155] bg-white dark:bg-[#0c0d12] text-ink-950 dark:text-white placeholder-ink-400 focus:outline-hidden focus:ring-2 focus:ring-navy-600"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="intendedDataTypes" className="block text-xs font-semibold text-ink-800 dark:text-ink-200 mb-1">
                  Intended Research Scope / Domain
                </label>
                <select
                  id="intendedDataTypes"
                  value={intendedDataTypes}
                  onChange={(e) => setIntendedDataTypes(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-[#CBD5E1] dark:border-[#334155] bg-white dark:bg-[#0c0d12] text-ink-950 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-navy-600"
                >
                  <option value="academic_papers">Academic & Peer-Reviewed Literature (EPR, Circular Economy)</option>
                  <option value="policy_frameworks">Environmental Policy & Legislative Frameworks</option>
                  <option value="empirical_data">Life Cycle Assessment & Empirical Studies</option>
                  <option value="general_scholarly">General Scientific Research</option>
                </select>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label htmlFor="researchPurpose" className="block text-xs font-semibold text-ink-800 dark:text-ink-200">
                    Purpose of Use & Research Topic <span className="text-rose-500">*</span>
                  </label>
                  <span className="text-[11px] text-ink-500 font-mono">
                    {researchPurpose.length} / 2000 chars (min 10)
                  </span>
                </div>
                <textarea
                  id="researchPurpose"
                  required
                  rows={4}
                  value={researchPurpose}
                  onChange={(e) => setResearchPurpose(e.target.value)}
                  placeholder="Describe your research methodology, topics of interest, and why access to ORION's multi-document RAG workspace is required..."
                  className="w-full p-3 text-xs rounded-lg border border-[#CBD5E1] dark:border-[#334155] bg-white dark:bg-[#0c0d12] text-ink-950 dark:text-white placeholder-ink-400 focus:outline-hidden focus:ring-2 focus:ring-navy-600 leading-relaxed resize-y"
                />
              </div>

              <button
                type="submit"
                disabled={isSubmitting || researchPurpose.trim().length < 10}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-navy-800 hover:bg-navy-900 text-white text-xs font-semibold shadow-subtle transition-all disabled:opacity-50 cursor-pointer"
              >
                {isSubmitting ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <Send className="w-3.5 h-3.5" />
                    <span>Submit Access Request</span>
                  </>
                )}
              </button>
            </form>
          )}

          {/* Invitation Redemption Expander for any state */}
          {accessStatus !== 'approved_invitation_pending' && (
            <div className="mt-8 pt-6 border-t border-[#E2E8F0] dark:border-[#1E293B]">
              <button
                type="button"
                onClick={() => setShowRedeemCard(!showRedeemCard)}
                className="flex items-center justify-between w-full text-xs font-semibold text-navy-700 dark:text-navy-400 hover:text-navy-900 transition-colors"
              >
                <span className="flex items-center gap-1.5">
                  <KeyRound className="w-3.5 h-3.5" />
                  <span>Have an Invitation Code? Redeem here</span>
                </span>
                <span className="text-[11px] font-mono">{showRedeemCard ? 'Hide' : 'Show'}</span>
              </button>

              {showRedeemCard && (
                <form onSubmit={handleRedeemInvitation} className="mt-4 flex flex-col sm:flex-row gap-2">
                  <input
                    type="text"
                    required
                    value={invitationToken}
                    onChange={(e) => setInvitationToken(e.target.value)}
                    placeholder="Enter invitation token..."
                    className="flex-1 px-3 py-2 text-xs rounded-lg border border-[#CBD5E1] dark:border-[#334155] bg-white dark:bg-[#0c0d12] text-ink-950 dark:text-white placeholder-ink-400 focus:outline-hidden focus:ring-2 focus:ring-navy-600 font-mono"
                  />
                  <button
                    type="submit"
                    disabled={isRedeeming || !invitationToken.trim()}
                    className="px-4 py-2 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold shadow-subtle transition-all disabled:opacity-50 shrink-0"
                  >
                    {isRedeeming ? 'Redeeming...' : 'Redeem Token'}
                  </button>
                </form>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

