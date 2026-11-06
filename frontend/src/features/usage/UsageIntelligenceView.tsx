import React, { useState, useEffect } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Cpu,
  Gauge,
  Info,
  RefreshCw,
  RotateCcw,
  Save,
  ShieldCheck,
  TrendingUp,
  Zap,
} from 'lucide-react';
import { api } from '../../services/api';
import {
  LLMQuotaResponse,
  LLMQuestionBudgetEstimate,
  LLMQuotaConfigUpdate,
} from '../../types';

export const UsageIntelligenceView: React.FC = () => {
  const [quota, setQuota] = useState<LLMQuotaResponse | null>(null);
  const [estimate, setEstimate] = useState<LLMQuestionBudgetEstimate | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Editable configuration state
  const [rpmInput, setRpmInput] = useState<number>(15);
  const [tpmInput, setTpmInput] = useState<number>(250000);
  const [rpdInput, setRpdInput] = useState<number>(500);
  const [warningThresholdInput, setWarningThresholdInput] = useState<number>(80);
  const [safetyMarginInput, setSafetyMarginInput] = useState<number>(10);
  const [timezoneInput, setTimezoneInput] = useState<string>('America/Los_Angeles');

  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [saveSuccessMessage, setSaveSuccessMessage] = useState<string | null>(null);
  const [saveErrorMessage, setSaveErrorMessage] = useState<string | null>(null);

  const fetchData = async (isManualRefresh = false) => {
    if (isManualRefresh) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }
    setError(null);
    setSaveSuccessMessage(null);
    setSaveErrorMessage(null);

    try {
      const [quotaData, estimateData] = await Promise.all([
        api.getLlmQuota(),
        api.getLlmQuotaEstimate(),
      ]);
      setQuota(quotaData);
      setEstimate(estimateData);

      // Initialize form with fetched values
      setRpmInput(quotaData.rpm_limit);
      setTpmInput(quotaData.tpm_limit);
      setRpdInput(quotaData.rpd_limit);
      setWarningThresholdInput(Math.round(quotaData.warning_threshold_percent * 100));
      setSafetyMarginInput(Math.round(quotaData.safety_margin_percent * 100));
      setTimezoneInput(quotaData.quota_timezone);
    } catch (err: any) {
      console.error('Failed to load LLM quota and estimate data:', err);
      setError(err?.message || 'Failed to retrieve LLM quota metrics from backend.');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setSaveSuccessMessage(null);
    setSaveErrorMessage(null);

    try {
      const payload: LLMQuotaConfigUpdate = {
        rpm_limit: Number(rpmInput),
        tpm_limit: Number(tpmInput),
        rpd_limit: Number(rpdInput),
        warning_threshold_percent: Number(warningThresholdInput) / 100,
        safety_margin_percent: Number(safetyMarginInput) / 100,
        quota_timezone: timezoneInput.trim(),
      };

      const updatedQuota = await api.updateLlmQuota(payload);
      setQuota(updatedQuota);

      // Re-fetch budget estimate so calculations reflect new limits
      const updatedEstimate = await api.getLlmQuotaEstimate();
      setEstimate(updatedEstimate);

      setSaveSuccessMessage('Reference quota limits updated successfully.');
    } catch (err: any) {
      console.error('Failed to update quota limits:', err);
      setSaveErrorMessage(err?.message || 'Failed to save quota configuration.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleResetDefaults = () => {
    setRpmInput(15);
    setTpmInput(250000);
    setRpdInput(500);
    setWarningThresholdInput(80);
    setSafetyMarginInput(10);
    setTimezoneInput('America/Los_Angeles');
    setSaveSuccessMessage(null);
    setSaveErrorMessage(null);
  };

  if (isLoading && !quota) {
    return (
      <div
        data-testid="usage-loading-state"
        className="p-8 md:p-12 max-w-6xl mx-auto flex flex-col items-center justify-center min-h-[420px] text-center"
      >
        <RefreshCw className="w-10 h-10 text-reading-primary animate-spin mb-4" />
        <h2 className="text-xl font-serif font-semibold text-ink">
          Loading Usage & Budget Intelligence...
        </h2>
        <p className="text-sm sm:text-[15px] text-ink-muted mt-2 max-w-md leading-relaxed">
          Retrieving persistent Gemini generation audit records, rolling minute throughput, and daily capacity projections.
        </p>
      </div>
    );
  }

  if (error && !quota) {
    return (
      <div
        data-testid="usage-error-state"
        className="p-8 md:p-10 max-w-4xl mx-auto my-8 bg-paper-surface rounded-2xl border border-border-hairline text-center shadow-subtle"
      >
        <AlertTriangle className="w-12 h-12 text-amber-600 dark:text-amber-400 mx-auto mb-4" />
        <h2 className="text-xl font-serif font-bold text-ink">
          Unable to Load Usage Intelligence
        </h2>
        <p className="text-sm sm:text-[15px] text-ink-secondary mt-2 max-w-md mx-auto leading-relaxed">
          {error}
        </p>
        <button
          type="button"
          onClick={() => fetchData()}
          className="mt-6 inline-flex items-center gap-2 px-5 py-2.5 bg-reading-primary text-white rounded-xl text-sm font-medium hover:bg-reading-primary/90 transition-colors shadow-subtle"
        >
          <RefreshCw className="w-4 h-4" />
          Retry Connection
        </button>
      </div>
    );
  }

  const confidenceBadgeColor = {
    low: 'bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-950/60 dark:text-amber-200 dark:border-amber-700',
    medium: 'bg-blue-100 text-blue-900 border-blue-300 dark:bg-blue-950/60 dark:text-blue-200 dark:border-blue-700',
    high: 'bg-emerald-100 text-emerald-900 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-200 dark:border-emerald-700',
  }[estimate?.confidence || 'low'];

  return (
    <div
      data-testid="usage-intelligence-dashboard"
      className="p-4 sm:p-6 md:p-8 max-w-6xl mx-auto space-y-6 sm:space-y-8 animate-fade-in text-ink"
    >
      {/* Top Header & Refresh Bar */}
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-5 border-b border-border-hairline">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <span className="p-2 rounded-xl bg-reading-primary/10 text-reading-primary">
              <Activity className="w-6 h-6" />
            </span>
            <h1 className="text-2xl sm:text-3xl font-serif font-bold text-ink tracking-tight">
              Usage & Question Budget Intelligence
            </h1>
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs sm:text-[13px] font-mono font-medium bg-paper-raised text-ink border border-border-hairline">
              <Cpu className="w-3.5 h-3.5 text-reading-primary" />
              {quota?.model_id}
            </span>
          </div>
          <p className="text-sm sm:text-[15px] text-ink-muted mt-2 max-w-2xl leading-relaxed">
            Live provider generation audit, daily research capacity projections, rolling-minute throughput limits, and configurable quota controls.
          </p>
        </div>

        <div className="flex items-center gap-4 shrink-0">
          {quota?.last_updated_at && (
            <div className="text-right hidden sm:block">
              <p className="text-xs font-medium text-ink-muted uppercase tracking-wider">Last Synchronized</p>
              <p className="text-sm font-mono text-ink-secondary mt-0.5">
                {new Date(quota.last_updated_at).toLocaleTimeString()}
              </p>
            </div>
          )}
          <button
            type="button"
            onClick={() => fetchData(true)}
            disabled={isRefreshing}
            aria-label="Refresh usage data"
            className="flex items-center gap-2 px-4 py-2 bg-paper-surface hover:bg-paper-raised text-ink border border-border-hairline rounded-xl text-sm font-medium transition-all shadow-subtle disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>{isRefreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>
        </div>
      </header>

      {/* External Quota Disclosure Banner */}
      <div
        data-testid="quota-disclaimer-banner"
        className="flex items-start gap-4 p-5 sm:p-6 rounded-2xl bg-paper-raised border border-border-hairline shadow-subtle"
      >
        <Info className="w-5 h-5 text-reading-primary shrink-0 mt-0.5 sm:mt-1" />
        <div className="space-y-1.5 flex-1">
          <h3 className="text-[17px] sm:text-lg font-serif font-semibold text-ink">
            Reference Quota Accounting Disclosure
          </h3>
          <p className="text-[15px] sm:text-base text-ink-secondary leading-relaxed">
            {quota?.quota_source_disclaimer ||
              "Configured reference limits are based on your Google AI Studio tier. ORION does not have access to Google's server-side account balance. External applications sharing this API key may consume quota independently."}
          </p>
        </div>
      </div>

      {/* Grid: Section A & Section B */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 sm:gap-8">
        {/* SECTION A: Daily Question Budget (RPD Horizon) */}
        <section
          data-testid="daily-question-budget-section"
          className="bg-paper-surface p-6 sm:p-7 lg:p-8 rounded-2xl border border-border-hairline shadow-subtle flex flex-col justify-between space-y-6"
        >
          <div>
            <div className="flex items-center justify-between gap-3 border-b border-border-hairline pb-4">
              <div className="flex items-center gap-2.5">
                <span className="p-1.5 rounded-lg bg-reading-primary/10 text-reading-primary">
                  <Gauge className="w-5 h-5" />
                </span>
                <h2 className="text-xl sm:text-[22px] font-serif font-semibold text-ink">
                  Daily Question Budget (RPD Horizon)
                </h2>
              </div>
              <span
                data-testid="confidence-badge"
                className={`px-3 py-1 rounded-full text-xs sm:text-[13px] font-semibold border ${confidenceBadgeColor}`}
              >
                {estimate?.confidence?.toUpperCase()} CONFIDENCE
              </span>
            </div>

            {/* Primary Daily Figure */}
            <div className="mt-5 flex items-baseline justify-between gap-4">
              <div>
                <p className="text-sm sm:text-[15px] font-medium text-ink-muted uppercase tracking-wider">
                  Conservative Remaining Today
                </p>
                <div className="flex items-baseline gap-2.5 mt-1.5">
                  <span
                    data-testid="daily-questions-remaining"
                    className="text-5xl xs:text-6xl sm:text-[58px] lg:text-[64px] font-serif font-bold text-ink tracking-tight"
                  >
                    {estimate?.daily_questions_remaining ?? '—'}
                  </span>
                  <span className="text-sm sm:text-base font-sans font-medium text-ink-muted">
                    questions
                  </span>
                </div>
              </div>

              <div className="text-right">
                <p className="text-sm sm:text-[15px] font-medium text-ink-muted uppercase tracking-wider">
                  Daily Utilization
                </p>
                <p
                  data-testid="daily-rpd-utilization"
                  className="text-2xl sm:text-[26px] font-serif font-bold text-ink mt-1.5"
                >
                  {quota?.daily_usage.rpd_utilization_percent ?? 0}%
                </p>
                <p className="text-xs sm:text-sm text-ink-muted font-mono mt-0.5">
                  {quota?.daily_usage.total_provider_attempts_today ?? 0} / {quota?.rpd_limit ?? 500} calls
                </p>
              </div>
            </div>

            {/* Progress Bar for RPD */}
            <div className="mt-4 w-full bg-paper-raised h-3 sm:h-3.5 rounded-full overflow-hidden border border-border-hairline">
              <div
                className="bg-reading-primary h-full rounded-full transition-all duration-500"
                style={{
                  width: `${Math.min(100, Math.max(0, quota?.daily_usage.rpd_utilization_percent ?? 0))}%`,
                }}
              />
            </div>

            {/* Sub-estimates */}
            <div className="grid grid-cols-2 gap-4 mt-5 pt-5 border-t border-border-hairline">
              <div className="p-4 rounded-xl bg-paper-card border border-border-hairline flex flex-col justify-between min-h-[105px] shadow-2xs space-y-1">
                <p className="text-sm sm:text-[15px] font-medium text-ink-secondary">Typical Estimate</p>
                <p
                  data-testid="daily-questions-typical"
                  className="text-2xl sm:text-[28px] font-serif font-semibold text-ink my-auto py-0.5"
                >
                  {estimate?.daily_questions_typical ?? '—'}
                </p>
                <p className="text-[13px] sm:text-sm text-ink-muted">Based on average tokens & retries</p>
              </div>
              <div className="p-4 rounded-xl bg-paper-card border border-border-hairline flex flex-col justify-between min-h-[105px] shadow-2xs space-y-1">
                <p className="text-sm sm:text-[15px] font-medium text-ink-secondary">Optimistic Estimate</p>
                <p
                  data-testid="daily-questions-optimistic"
                  className="text-2xl sm:text-[28px] font-serif font-semibold text-ink my-auto py-0.5"
                >
                  {estimate?.daily_questions_optimistic ?? '—'}
                </p>
                <p className="text-[13px] sm:text-sm text-ink-muted">Assumes efficient context & 0 retries</p>
              </div>
            </div>
          </div>

          {/* Daily Accounting Details */}
          <div className="pt-4 border-t border-border-hairline flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-sm text-ink-secondary">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
              <span>Questions Processed Today:</span>
              <strong
                data-testid="unique-questions-today"
                className="text-ink font-mono text-base font-semibold"
              >
                {quota?.daily_usage.unique_questions_today ?? 0}
              </strong>
            </div>
            <div className="text-right">
              <span className="text-xs sm:text-sm text-ink-muted">Governed by: </span>
              <span
                data-testid="daily-limiting-quota"
                className="font-mono font-semibold text-ink text-sm sm:text-base"
              >
                {estimate?.daily_limiting_quota || 'RPD'}
              </span>
            </div>
          </div>
        </section>

        {/* SECTION B: Immediate Throughput Capacity (Rolling 60s Horizon) */}
        <section
          data-testid="immediate-capacity-section"
          className="bg-paper-surface p-6 sm:p-7 lg:p-8 rounded-2xl border border-border-hairline shadow-subtle flex flex-col justify-between space-y-6"
        >
          <div>
            <div className="flex items-center justify-between gap-3 border-b border-border-hairline pb-4">
              <div className="flex items-center gap-2.5">
                <span className="p-1.5 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400">
                  <Zap className="w-5 h-5" />
                </span>
                <h2 className="text-xl sm:text-[22px] font-serif font-semibold text-ink">
                  Immediate Capacity (Rolling 60s)
                </h2>
              </div>
              <span
                data-testid="immediate-limiting-quota"
                className="px-3 py-1 rounded-full text-xs sm:text-[13px] font-mono font-bold bg-amber-100 text-amber-900 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300 dark:border-amber-700"
              >
                THROTTLED BY {estimate?.immediate_limiting_quota || 'RPM'}
              </span>
            </div>

            <p className="text-[15px] sm:text-base text-ink-secondary mt-3 leading-relaxed">
              Capacity executable within the current rolling 60-second window. This is immediate burst throughput, <em>not</em> your remaining daily allowance.
            </p>

            {/* Primary Immediate Figure */}
            <div className="mt-5 flex items-baseline justify-between gap-4">
              <div>
                <p className="text-sm sm:text-[15px] font-medium text-ink-muted uppercase tracking-wider">
                  Conservative Immediate Burst
                </p>
                <div className="flex items-baseline gap-2.5 mt-1.5">
                  <span
                    data-testid="immediate-questions-conservative"
                    className="text-5xl xs:text-6xl sm:text-[58px] lg:text-[64px] font-serif font-bold text-ink tracking-tight"
                  >
                    {estimate?.immediate_questions_conservative ?? '—'}
                  </span>
                  <span className="text-sm sm:text-base font-sans font-medium text-ink-muted">
                    questions now
                  </span>
                </div>
              </div>

              <div className="text-right">
                <p className="text-sm sm:text-[15px] font-medium text-ink-muted uppercase tracking-wider">
                  Rolling RPM Used
                </p>
                <p
                  data-testid="rolling-rpm-utilization"
                  className="text-2xl sm:text-[26px] font-serif font-bold text-ink mt-1.5"
                >
                  {quota?.rolling_usage.rpm_utilization_percent ?? 0}%
                </p>
                <p className="text-xs sm:text-sm text-ink-muted font-mono mt-0.5">
                  {quota?.rolling_usage.rolling_60s_requests ?? 0} / {quota?.rpm_limit ?? 15} RPM
                </p>
              </div>
            </div>

            {/* Dual Utilization Progress Gauges */}
            <div className="mt-5 space-y-3.5">
              <div>
                <div className="flex justify-between text-xs sm:text-sm text-ink-secondary mb-1.5">
                  <span className="font-medium">Rolling Requests (RPM)</span>
                  <span className="font-mono text-ink font-semibold">
                    {estimate?.rolling_requests_remaining ?? 0} usable remaining
                  </span>
                </div>
                <div className="w-full bg-paper-raised h-3 sm:h-3.5 rounded-full overflow-hidden border border-border-hairline">
                  <div
                    className="bg-amber-500 h-full rounded-full transition-all duration-300"
                    style={{
                      width: `${Math.min(100, Math.max(0, quota?.rolling_usage.rpm_utilization_percent ?? 0))}%`,
                    }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs sm:text-sm text-ink-secondary mb-1.5">
                  <span className="font-medium">Rolling Tokens (TPM)</span>
                  <span className="font-mono text-ink font-semibold">
                    {estimate?.rolling_tokens_remaining?.toLocaleString() ?? 0} tokens remaining
                  </span>
                </div>
                <div className="w-full bg-paper-raised h-3 sm:h-3.5 rounded-full overflow-hidden border border-border-hairline">
                  <div
                    className="bg-reading-primary h-full rounded-full transition-all duration-300"
                    style={{
                      width: `${Math.min(100, Math.max(0, quota?.rolling_usage.tpm_utilization_percent ?? 0))}%`,
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Sub-estimates */}
            <div className="grid grid-cols-2 gap-4 mt-5 pt-4 border-t border-border-hairline">
              <div className="p-4 rounded-xl bg-paper-card border border-border-hairline flex flex-col justify-between min-h-[105px] shadow-2xs space-y-1">
                <p className="text-sm sm:text-[15px] font-medium text-ink-secondary">Typical Immediate</p>
                <p
                  data-testid="immediate-questions-typical"
                  className="text-2xl sm:text-[28px] font-serif font-semibold text-ink my-auto py-0.5"
                >
                  {estimate?.immediate_questions_typical ?? '—'}
                </p>
                <p className="text-[13px] sm:text-sm text-ink-muted">Expected 60s throughput</p>
              </div>
              <div className="p-4 rounded-xl bg-paper-card border border-border-hairline flex flex-col justify-between min-h-[105px] shadow-2xs space-y-1">
                <p className="text-sm sm:text-[15px] font-medium text-ink-secondary">Optimistic Immediate</p>
                <p
                  data-testid="immediate-questions-optimistic"
                  className="text-2xl sm:text-[28px] font-serif font-semibold text-ink my-auto py-0.5"
                >
                  {estimate?.immediate_questions_optimistic ?? '—'}
                </p>
                <p className="text-[13px] sm:text-sm text-ink-muted">Max concurrency burst</p>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-border-hairline text-sm text-ink-secondary flex items-center justify-between">
            <span>Safety Margin Applied:</span>
            <strong className="font-mono text-ink text-sm sm:text-base font-semibold">
              {Math.round((quota?.safety_margin_percent ?? 0.1) * 100)}%
            </strong>
          </div>
        </section>
      </div>

      {/* Grid: Section C & Section D */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 sm:gap-8">
        {/* SECTION C: Token Analytics */}
        <section
          data-testid="token-analytics-section"
          className="usage-card-container bg-paper-surface p-6 sm:p-7 lg:p-8 rounded-2xl border border-border-hairline shadow-subtle space-y-6"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border-hairline pb-4">
            <div className="flex items-center gap-2.5 min-w-0">
              <span className="p-1.5 rounded-lg bg-blue-500/10 text-reading-primary shrink-0">
                <TrendingUp className="w-5 h-5" />
              </span>
              <h2 className="text-xl sm:text-[22px] font-serif font-semibold text-ink truncate">
                Token Analytics & Efficiency
              </h2>
            </div>
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs sm:text-[13px] font-mono font-semibold bg-paper-raised text-ink border border-border-hairline shadow-2xs shrink-0 whitespace-nowrap self-start sm:self-auto">
              <span className="text-ink-muted font-medium">Sample Size:</span>
              <span className="text-ink font-bold">{estimate?.sample_size ?? 0}</span>
            </span>
          </div>

          <div className="grid grid-cols-1 xs:grid-cols-3 gap-4">
            <div className="p-4 sm:p-5 rounded-xl bg-paper-card border border-border-hairline flex flex-col justify-between min-h-[128px] shadow-2xs">
              <p className="text-sm sm:text-[15px] font-medium text-ink-muted uppercase tracking-wider">
                Prompt Tokens
              </p>
              <p
                data-testid="prompt-tokens-today"
                className="text-[28px] sm:text-[32px] font-serif font-bold text-ink my-auto py-1"
              >
                {quota?.daily_usage.prompt_tokens_today.toLocaleString() ?? '0'}
              </p>
              <p className="text-[13px] sm:text-sm text-ink-muted font-mono pt-1">
                Avg: {estimate?.average_prompt_tokens.toLocaleString() ?? '—'}
              </p>
            </div>

            <div className="p-4 sm:p-5 rounded-xl bg-paper-card border border-border-hairline flex flex-col justify-between min-h-[128px] shadow-2xs">
              <p className="text-sm sm:text-[15px] font-medium text-ink-muted uppercase tracking-wider">
                Completion Tokens
              </p>
              <p
                data-testid="completion-tokens-today"
                className="text-[28px] sm:text-[32px] font-serif font-bold text-ink my-auto py-1"
              >
                {quota?.daily_usage.completion_tokens_today.toLocaleString() ?? '0'}
              </p>
              <p className="text-[13px] sm:text-sm text-ink-muted font-mono pt-1">
                Avg: {estimate?.average_completion_tokens.toLocaleString() ?? '—'}
              </p>
            </div>

            <div className="p-4 sm:p-5 rounded-xl bg-paper-card border border-border-hairline flex flex-col justify-between min-h-[128px] shadow-2xs">
              <p className="text-sm sm:text-[15px] font-medium text-ink-muted uppercase tracking-wider">
                Total Tokens
              </p>
              <p
                data-testid="total-tokens-today"
                className="text-[28px] sm:text-[32px] font-serif font-bold text-ink my-auto py-1"
              >
                {quota?.daily_usage.total_tokens_today.toLocaleString() ?? '0'}
              </p>
              <p className="text-[13px] sm:text-sm text-ink-muted font-mono pt-1">
                Avg: {estimate?.average_total_tokens.toLocaleString() ?? '—'}
              </p>
            </div>
          </div>

          {/* Honest Historical Trend Notice */}
          <div
            data-testid="historical-trend-notice"
            className="p-4 sm:p-5 rounded-xl bg-paper-raised border border-border-hairline text-sm sm:text-[15px] text-ink-secondary leading-relaxed"
          >
            {estimate?.is_fallback_estimate ? (
              <p className="flex items-start gap-2.5">
                <Clock className="w-5 h-5 text-ink-muted shrink-0 mt-0.5" />
                <span>
                  Historical daily/weekly trend charts activate after ≥5 grounded generations are recorded. Current statistics use conservative baseline distributions (low sample size: {estimate.sample_size} call).
                </span>
              </p>
            ) : (
              <div className="space-y-2">
                <p className="font-semibold text-ink text-sm sm:text-base">
                  Calibrated Token Ratio
                </p>
                <div className="w-full bg-paper-surface h-3 rounded-full overflow-hidden flex border border-border-hairline">
                  <div
                    className="bg-blue-600 h-full"
                    style={{
                      width: `${
                        ((estimate?.average_prompt_tokens ?? 3500) /
                          Math.max(1, estimate?.average_total_tokens ?? 5300)) *
                        100
                      }%`,
                    }}
                    title="Prompt Tokens"
                  />
                  <div
                    className="bg-emerald-600 h-full"
                    style={{
                      width: `${
                        ((estimate?.average_completion_tokens ?? 1800) /
                          Math.max(1, estimate?.average_total_tokens ?? 5300)) *
                        100
                      }%`,
                    }}
                    title="Completion Tokens"
                  />
                </div>
                <div className="flex justify-between text-xs sm:text-sm text-ink-muted font-mono pt-1">
                  <span>Prompt: {estimate?.average_prompt_tokens?.toLocaleString()}</span>
                  <span>Completion: {estimate?.average_completion_tokens?.toLocaleString()}</span>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* SECTION D: Provider Reliability & Diagnostics */}
        <section
          data-testid="provider-reliability-section"
          className="usage-card-container bg-paper-surface p-6 sm:p-7 lg:p-8 rounded-2xl border border-border-hairline shadow-subtle space-y-6"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border-hairline pb-4">
            <div className="flex items-center gap-2.5 min-w-0">
              <span className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shrink-0">
                <ShieldCheck className="w-5 h-5" />
              </span>
              <h2 className="text-xl sm:text-[22px] font-serif font-semibold text-ink truncate">
                Provider Reliability & Call Audit
              </h2>
            </div>
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs sm:text-[13px] font-mono font-semibold bg-paper-raised text-ink border border-border-hairline shadow-2xs shrink-0 whitespace-nowrap self-start sm:self-auto">
              <span className="text-ink-muted font-medium">Attempt Ratio:</span>
              <span className="text-ink font-bold">{estimate?.attempts_per_question ?? 1.0}x</span>
            </span>
          </div>

          <div className="reliability-metric-grid">
            <div className="p-4 sm:p-5 rounded-xl bg-emerald-50/70 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 flex flex-col justify-between min-h-[128px] text-center shadow-2xs">
              <p className="text-sm sm:text-[15px] text-emerald-800 dark:text-emerald-300 font-medium whitespace-nowrap">Successful</p>
              <p
                data-testid="successful-generations"
                className="text-[28px] sm:text-[32px] font-serif font-bold text-emerald-900 dark:text-emerald-200 my-auto py-1"
              >
                {quota?.daily_usage.successful_generations_today ?? 0}
              </p>
              <p className="text-[13px] sm:text-sm text-emerald-700/80 dark:text-emerald-400 whitespace-nowrap">Gemini calls</p>
            </div>

            <div className="p-4 sm:p-5 rounded-xl bg-amber-50/70 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 flex flex-col justify-between min-h-[128px] text-center shadow-2xs">
              <p className="text-sm sm:text-[15px] text-amber-800 dark:text-amber-300 font-medium whitespace-nowrap">Failed Attempts</p>
              <p
                data-testid="failed-attempts"
                className="text-[28px] sm:text-[32px] font-serif font-bold text-amber-900 dark:text-amber-200 my-auto py-1"
              >
                {quota?.daily_usage.failed_provider_attempts_today ?? 0}
              </p>
              <p className="text-[13px] sm:text-sm text-amber-700/80 dark:text-amber-400 whitespace-nowrap">HTTP/429 errors</p>
            </div>

            <div className="p-4 sm:p-5 rounded-xl bg-paper-card border border-border-hairline flex flex-col justify-between min-h-[128px] text-center shadow-2xs">
              <p className="text-sm sm:text-[15px] text-ink-secondary font-medium whitespace-nowrap">Deterministic</p>
              <p
                data-testid="fallback-events"
                className="text-[28px] sm:text-[32px] font-serif font-bold text-ink my-auto py-1"
              >
                {quota?.daily_usage.fallback_events_today ?? 0}
              </p>
              <p className="text-[13px] sm:text-sm text-ink-muted whitespace-nowrap">Fallbacks</p>
            </div>

            <div className="p-4 sm:p-5 rounded-xl bg-paper-card border border-border-hairline flex flex-col justify-between min-h-[128px] text-center shadow-2xs">
              <p className="text-sm sm:text-[15px] text-ink-secondary font-medium whitespace-nowrap">Cache / Abstain</p>
              <p
                data-testid="cache-abstain-events"
                className="text-[28px] sm:text-[32px] font-serif font-bold text-ink my-auto py-1"
              >
                0
              </p>
              <p className="text-[13px] sm:text-sm text-ink-muted whitespace-nowrap">Non-billed calls</p>
            </div>
          </div>

          <div className="pt-4 text-xs sm:text-sm text-ink-secondary flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-t border-border-hairline">
            <span className="text-ink-muted">Deterministic fallbacks and cache hits:</span>
            <span className="font-semibold text-ink sm:text-right">
              Excluded from provider billing
            </span>
          </div>
        </section>
      </div>

      {/* SECTION E: Quota Configuration & Safety Controls */}
      <section
        data-testid="quota-configuration-section"
        className="bg-paper-surface p-6 sm:p-7 lg:p-8 rounded-2xl border border-border-hairline shadow-subtle space-y-6"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border-hairline pb-4">
          <div>
            <h2 className="text-xl sm:text-[22px] font-serif font-semibold text-ink">
              Configured Reference Limits & Safety Margins
            </h2>
            <p className="text-sm sm:text-[15px] text-ink-muted mt-1 leading-relaxed">
              Adjustable local baseline parameters for your Google AI Studio tier. Modifying these limits tunes ORION's warnings and capacity estimators.
            </p>
          </div>
          <button
            type="button"
            onClick={handleResetDefaults}
            className="self-start sm:self-auto flex items-center gap-2 px-3.5 py-2 rounded-xl border border-border-hairline text-xs sm:text-sm font-medium text-ink bg-paper-card hover:bg-paper-raised transition-colors shadow-subtle"
          >
            <RotateCcw className="w-4 h-4 text-reading-primary" />
            <span>Restore ORION Reference Defaults</span>
          </button>
        </div>

        {saveSuccessMessage && (
          <div
            data-testid="save-success-banner"
            className="p-4 rounded-xl bg-emerald-100 text-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-200 border border-emerald-300 dark:border-emerald-700 text-sm flex items-center gap-2.5"
          >
            <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
            <span>{saveSuccessMessage}</span>
          </div>
        )}

        {saveErrorMessage && (
          <div
            data-testid="save-error-banner"
            className="p-4 rounded-xl bg-red-100 text-red-900 dark:bg-red-950/60 dark:text-red-200 border border-red-300 dark:border-red-700 text-sm flex items-center gap-2.5"
          >
            <AlertTriangle className="w-5 h-5 text-red-600 shrink-0" />
            <span>{saveErrorMessage}</span>
          </div>
        )}

        <form onSubmit={handleSaveConfig} className="space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            <div>
              <label htmlFor="rpm-input" className="block text-sm sm:text-[15px] font-medium text-ink mb-1.5">
                Requests Per Minute (RPM)
              </label>
              <input
                id="rpm-input"
                type="number"
                min="1"
                max="10000"
                value={rpmInput}
                onChange={(e) => setRpmInput(Number(e.target.value))}
                className="w-full px-3.5 py-2.5 bg-paper-card border border-border-hairline rounded-xl text-ink focus:outline-hidden focus:ring-2 focus:ring-reading-primary font-mono text-sm sm:text-base"
                required
              />
              <span className="text-xs sm:text-sm text-ink-muted mt-1.5 block">
                Default: 15 RPM for Gemini 3.5 Flash-Lite
              </span>
            </div>

            <div>
              <label htmlFor="tpm-input" className="block text-sm sm:text-[15px] font-medium text-ink mb-1.5">
                Tokens Per Minute (TPM)
              </label>
              <input
                id="tpm-input"
                type="number"
                min="1000"
                max="50000000"
                step="1000"
                value={tpmInput}
                onChange={(e) => setTpmInput(Number(e.target.value))}
                className="w-full px-3.5 py-2.5 bg-paper-card border border-border-hairline rounded-xl text-ink focus:outline-hidden focus:ring-2 focus:ring-reading-primary font-mono text-sm sm:text-base"
                required
              />
              <span className="text-xs sm:text-sm text-ink-muted mt-1.5 block">
                Default: 250,000 TPM
              </span>
            </div>

            <div>
              <label htmlFor="rpd-input" className="block text-sm sm:text-[15px] font-medium text-ink mb-1.5">
                Requests Per Day (RPD)
              </label>
              <input
                id="rpd-input"
                type="number"
                min="1"
                max="100000"
                value={rpdInput}
                onChange={(e) => setRpdInput(Number(e.target.value))}
                className="w-full px-3.5 py-2.5 bg-paper-card border border-border-hairline rounded-xl text-ink focus:outline-hidden focus:ring-2 focus:ring-reading-primary font-mono text-sm sm:text-base"
                required
              />
              <span className="text-xs sm:text-sm text-ink-muted mt-1.5 block">
                Default: 500 RPD
              </span>
            </div>

            <div>
              <label htmlFor="warning-input" className="block text-sm sm:text-[15px] font-medium text-ink mb-1.5">
                Warning Threshold (%)
              </label>
              <input
                id="warning-input"
                type="number"
                min="10"
                max="100"
                value={warningThresholdInput}
                onChange={(e) => setWarningThresholdInput(Number(e.target.value))}
                className="w-full px-3.5 py-2.5 bg-paper-card border border-border-hairline rounded-xl text-ink focus:outline-hidden focus:ring-2 focus:ring-reading-primary font-mono text-sm sm:text-base"
                required
              />
              <span className="text-xs sm:text-sm text-ink-muted mt-1.5 block">
                Alert threshold before throttling (e.g. 80%)
              </span>
            </div>

            <div>
              <label htmlFor="margin-input" className="block text-sm sm:text-[15px] font-medium text-ink mb-1.5">
                Safety Reserve Margin (%)
              </label>
              <input
                id="margin-input"
                type="number"
                min="0"
                max="50"
                value={safetyMarginInput}
                onChange={(e) => setSafetyMarginInput(Number(e.target.value))}
                className="w-full px-3.5 py-2.5 bg-paper-card border border-border-hairline rounded-xl text-ink focus:outline-hidden focus:ring-2 focus:ring-reading-primary font-mono text-sm sm:text-base"
                required
              />
              <span className="text-xs sm:text-sm text-ink-muted mt-1.5 block">
                Reserve buffer deducted from usable limit (e.g. 10%)
              </span>
            </div>

            <div>
              <label htmlFor="timezone-input" className="block text-sm sm:text-[15px] font-medium text-ink mb-1.5">
                Quota Timezone
              </label>
              <input
                id="timezone-input"
                type="text"
                value={timezoneInput}
                onChange={(e) => setTimezoneInput(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-paper-card border border-border-hairline rounded-xl text-ink focus:outline-hidden focus:ring-2 focus:ring-reading-primary font-mono text-sm sm:text-base"
                required
              />
              <span className="text-xs sm:text-sm text-ink-muted mt-1.5 block">
                Google resets daily at midnight Pacific Time
              </span>
            </div>
          </div>

          <div className="pt-3 flex justify-end">
            <button
              type="submit"
              disabled={isSaving}
              data-testid="save-quota-button"
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-reading-primary hover:bg-reading-primary/90 text-white rounded-xl text-sm font-medium transition-all shadow-subtle disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              <span>{isSaving ? 'Saving Changes...' : 'Save Reference Limits'}</span>
            </button>
          </div>
        </form>
      </section>
    </div>
  );
};
