import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { UsageIntelligenceView } from '../src/features/usage/UsageIntelligenceView';
import { api } from '../src/services/api';
import { LLMQuotaResponse, LLMQuestionBudgetEstimate } from '../src/types';

const mockQuotaResponse: LLMQuotaResponse = {
  model_id: 'gemini-3.5-flash-lite',
  is_active_model: true,
  is_reference_quota: true,
  quota_source_disclaimer:
    "Configured reference limits based on Google AI Studio tier. ORION does not have real-time access to Google's server-side quota balance.",
  rpm_limit: 15,
  tpm_limit: 250000,
  rpd_limit: 500,
  quota_timezone: 'America/Los_Angeles',
  warning_threshold_percent: 0.8,
  safety_margin_percent: 0.1,
  last_updated_at: '2026-10-31T10:30:00Z',
  rolling_usage: {
    rolling_60s_requests: 2,
    rolling_60s_tokens: 8500,
    rpm_limit: 15,
    tpm_limit: 250000,
    rpm_utilization_percent: 13.33,
    tpm_utilization_percent: 3.4,
  },
  daily_usage: {
    quota_timezone: 'America/Los_Angeles',
    today_start_utc: '2026-10-31T07:00:00Z',
    unique_questions_today: 12,
    total_provider_attempts_today: 14,
    successful_generations_today: 13,
    failed_provider_attempts_today: 1,
    fallback_events_today: 2,
    prompt_tokens_today: 42000,
    completion_tokens_today: 18000,
    total_tokens_today: 60000,
    rpd_limit: 500,
    rpd_utilization_percent: 2.8,
  },
};

const mockEstimateResponse: LLMQuestionBudgetEstimate = {
  model_id: 'gemini-3.5-flash-lite',
  is_active_model: true,
  daily_questions_remaining: 375,
  daily_questions_typical: 410,
  daily_questions_optimistic: 436,
  daily_limiting_quota: 'RPD',
  immediate_questions_conservative: 9,
  immediate_questions_typical: 11,
  immediate_questions_optimistic: 11,
  immediate_limiting_quota: 'RPM',
  estimated_questions_remaining: 375,
  estimated_questions_typical: 410,
  estimated_questions_optimistic: 436,
  limiting_quota: 'RPD',
  rolling_questions_remaining: 9,
  remaining_requests_today: 436,
  remaining_tokens_today: null,
  rolling_requests_remaining: 11,
  rolling_tokens_remaining: 216500,
  average_prompt_tokens: 3200,
  average_completion_tokens: 1400,
  average_total_tokens: 4600,
  attempts_per_question: 1.17,
  sample_size: 13,
  confidence: 'medium',
  is_fallback_estimate: false,
  safety_margin_percent: 0.1,
  estimation_disclaimer:
    'Dynamic budget projection calculated from 13 real grounded generations.',
};

describe('UsageIntelligenceDashboard Component Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders loading state when initial data is in-flight', () => {
    vi.spyOn(api, 'getLlmQuota').mockImplementation(() => new Promise(() => {}));
    vi.spyOn(api, 'getLlmQuotaEstimate').mockImplementation(() => new Promise(() => {}));

    render(<UsageIntelligenceView />);

    expect(screen.getByTestId('usage-loading-state')).toBeDefined();
    expect(screen.getByText(/Loading Usage & Budget Intelligence/i)).toBeDefined();
  });

  it('renders error state with retry button on API failure', async () => {
    vi.spyOn(api, 'getLlmQuota').mockRejectedValue(new Error('Connection refused'));
    vi.spyOn(api, 'getLlmQuotaEstimate').mockRejectedValue(new Error('Connection refused'));

    render(<UsageIntelligenceView />);

    await waitFor(() => {
      expect(screen.getByTestId('usage-error-state')).toBeDefined();
    });
    expect(screen.getByText(/Unable to Load Usage Intelligence/i)).toBeDefined();
    expect(screen.getByText(/Connection refused/i)).toBeDefined();
  });

  it('renders full usage intelligence dashboard with API data', async () => {
    vi.spyOn(api, 'getLlmQuota').mockResolvedValue(mockQuotaResponse);
    vi.spyOn(api, 'getLlmQuotaEstimate').mockResolvedValue(mockEstimateResponse);

    render(<UsageIntelligenceView />);

    await waitFor(() => {
      expect(screen.getByTestId('usage-intelligence-dashboard')).toBeDefined();
    });

    expect(screen.getByText('Usage & Question Budget Intelligence')).toBeDefined();
    expect(screen.getByText('gemini-3.5-flash-lite')).toBeDefined();
    expect(screen.getByTestId('quota-disclaimer-banner')).toBeDefined();
  });

  it('distinctly separates daily RPD capacity from immediate rolling-minute capacity', async () => {
    vi.spyOn(api, 'getLlmQuota').mockResolvedValue(mockQuotaResponse);
    vi.spyOn(api, 'getLlmQuotaEstimate').mockResolvedValue(mockEstimateResponse);

    render(<UsageIntelligenceView />);

    await waitFor(() => {
      expect(screen.getByTestId('daily-question-budget-section')).toBeDefined();
      expect(screen.getByTestId('immediate-capacity-section')).toBeDefined();
    });

    // Daily capacity section checks
    expect(screen.getByTestId('daily-questions-remaining').textContent).toBe('375');
    expect(screen.getByTestId('daily-questions-typical').textContent).toBe('410');
    expect(screen.getByTestId('daily-questions-optimistic').textContent).toBe('436');
    expect(screen.getByTestId('daily-limiting-quota').textContent).toBe('RPD');
    expect(screen.getByTestId('unique-questions-today').textContent).toBe('12');

    // Immediate capacity section checks
    expect(screen.getByTestId('immediate-questions-conservative').textContent).toBe('9');
    expect(screen.getByTestId('immediate-questions-typical').textContent).toBe('11');
    expect(screen.getByTestId('immediate-questions-optimistic').textContent).toBe('11');
    expect(screen.getByTestId('immediate-limiting-quota').textContent).toContain('RPM');
  });

  it('displays low-confidence badge and explanation for small historical sample size', async () => {
    const lowSampleEstimate: LLMQuestionBudgetEstimate = {
      ...mockEstimateResponse,
      sample_size: 1,
      confidence: 'low',
      is_fallback_estimate: true,
      estimation_disclaimer:
        'Preliminary budget projection based on conservative baseline estimates (low sample size: 1 recorded).',
    };

    vi.spyOn(api, 'getLlmQuota').mockResolvedValue(mockQuotaResponse);
    vi.spyOn(api, 'getLlmQuotaEstimate').mockResolvedValue(lowSampleEstimate);

    render(<UsageIntelligenceView />);

    await waitFor(() => {
      expect(screen.getByTestId('confidence-badge').textContent).toContain('LOW');
    });

    expect(
      screen.getByText(/Historical daily\/weekly trend charts activate after ≥5 grounded generations/i)
    ).toBeDefined();
  });

  it('renders token analytics and provider reliability metrics accurately', async () => {
    vi.spyOn(api, 'getLlmQuota').mockResolvedValue(mockQuotaResponse);
    vi.spyOn(api, 'getLlmQuotaEstimate').mockResolvedValue(mockEstimateResponse);

    render(<UsageIntelligenceView />);

    await waitFor(() => {
      expect(screen.getByTestId('token-analytics-section')).toBeDefined();
      expect(screen.getByTestId('provider-reliability-section')).toBeDefined();
    });

    expect(screen.getByTestId('prompt-tokens-today').textContent).toBe('42,000');
    expect(screen.getByTestId('completion-tokens-today').textContent).toBe('18,000');
    expect(screen.getByTestId('total-tokens-today').textContent).toBe('60,000');

    expect(screen.getByTestId('successful-generations').textContent).toBe('13');
    expect(screen.getByTestId('failed-attempts').textContent).toBe('1');
    expect(screen.getByTestId('fallback-events').textContent).toBe('2');
  });

  it('allows updating quota configuration and displays success confirmation', async () => {
    vi.spyOn(api, 'getLlmQuota').mockResolvedValue(mockQuotaResponse);
    vi.spyOn(api, 'getLlmQuotaEstimate').mockResolvedValue(mockEstimateResponse);
    const updateSpy = vi.spyOn(api, 'updateLlmQuota').mockResolvedValue({
      ...mockQuotaResponse,
      rpm_limit: 20,
    });

    render(<UsageIntelligenceView />);

    await waitFor(() => {
      expect(screen.getByTestId('quota-configuration-section')).toBeDefined();
    });

    const rpmInput = screen.getByLabelText(/Requests Per Minute/i) as HTMLInputElement;
    fireEvent.change(rpmInput, { target: { value: '20' } });

    const saveButton = screen.getByTestId('save-quota-button');
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          rpm_limit: 20,
        })
      );
      expect(screen.getByTestId('save-success-banner')).toBeDefined();
      expect(screen.getByText(/Reference quota limits updated successfully/i)).toBeDefined();
    });
  });

  it('handles quota update errors and displays accessible error feedback', async () => {
    vi.spyOn(api, 'getLlmQuota').mockResolvedValue(mockQuotaResponse);
    vi.spyOn(api, 'getLlmQuotaEstimate').mockResolvedValue(mockEstimateResponse);
    vi.spyOn(api, 'updateLlmQuota').mockRejectedValue(new Error('Invalid timezone specified'));

    render(<UsageIntelligenceView />);

    await waitFor(() => {
      expect(screen.getByTestId('quota-configuration-section')).toBeDefined();
    });

    const saveButton = screen.getByTestId('save-quota-button');
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(screen.getByTestId('save-error-banner')).toBeDefined();
      expect(screen.getByText(/Invalid timezone specified/i)).toBeDefined();
    });
  });

  it('resets form values to AI Studio defaults on button click', async () => {
    vi.spyOn(api, 'getLlmQuota').mockResolvedValue({
      ...mockQuotaResponse,
      rpm_limit: 99,
      rpd_limit: 9999,
    });
    vi.spyOn(api, 'getLlmQuotaEstimate').mockResolvedValue(mockEstimateResponse);

    render(<UsageIntelligenceView />);

    await waitFor(() => {
      expect(screen.getByLabelText(/Requests Per Minute/i)).toBeDefined();
    });

    const rpmInput = screen.getByLabelText(/Requests Per Minute/i) as HTMLInputElement;
    expect(rpmInput.value).toBe('99');

    const resetBtn = screen.getByText(/Restore ORION Reference Defaults/i);
    fireEvent.click(resetBtn);

    expect(rpmInput.value).toBe('15');
    const rpdInput = screen.getByLabelText(/Requests Per Day/i) as HTMLInputElement;
    expect(rpdInput.value).toBe('500');
  });

  it('renders cleanly in dark theme mode', async () => {
    document.documentElement.classList.add('dark');
    vi.spyOn(api, 'getLlmQuota').mockResolvedValue(mockQuotaResponse);
    vi.spyOn(api, 'getLlmQuotaEstimate').mockResolvedValue(mockEstimateResponse);

    render(<UsageIntelligenceView />);

    await waitFor(() => {
      expect(screen.getByTestId('usage-intelligence-dashboard')).toBeDefined();
    });

    expect(document.documentElement.classList.contains('dark')).toBe(true);
    document.documentElement.classList.remove('dark');
  });

  it('adapts responsive layout at desktop, tablet, and mobile viewport widths', async () => {
    vi.spyOn(api, 'getLlmQuota').mockResolvedValue(mockQuotaResponse);
    vi.spyOn(api, 'getLlmQuotaEstimate').mockResolvedValue(mockEstimateResponse);

    // 1. Desktop (1440px)
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 1440 });
    window.dispatchEvent(new Event('resize'));
    const { rerender } = render(<UsageIntelligenceView />);

    await waitFor(() => {
      expect(screen.getByTestId('usage-intelligence-dashboard')).toBeDefined();
    });
    expect(screen.getByTestId('daily-question-budget-section')).toBeDefined();

    // 2. Tablet (820px)
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 820 });
    window.dispatchEvent(new Event('resize'));
    rerender(<UsageIntelligenceView />);
    expect(screen.getByTestId('immediate-capacity-section')).toBeDefined();

    // 3. Mobile (390px)
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 390 });
    window.dispatchEvent(new Event('resize'));
    rerender(<UsageIntelligenceView />);
    expect(screen.getByTestId('token-analytics-section')).toBeDefined();
  });
});

