import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AdminDashboardView } from '../src/features/admin/AdminDashboardView';
import { api } from '../src/services/api';

// Mock the API client
vi.mock('../src/services/api', () => ({
  api: {
    getAdminOverview: vi.fn(),
    getAdminSystemHealth: vi.fn(),
    getAdminRegistrationAnalytics: vi.fn(),
    getAdminLoginAnalytics: vi.fn(),
    getAdminAIUsageAnalytics: vi.fn(),
    getAdminUsers: vi.fn(),
    getAdminUserDetail: vi.fn(),
    getAdminUserActivity: vi.fn(),
  },
}));

describe('Admin Dashboard UI Component Tests', () => {
  const mockOverview = {
    users: {
      total_users: 12,
      active_users_24h: 4,
      active_users_7d: 8,
      active_users_30d: 11,
      new_users_today: 2,
      new_users_this_week: 5,
      new_users_this_month: 12,
    },
    logins: {
      total_logins: 48,
      logins_today: 9,
      logins_this_week: 32,
      failed_logins_today: 1,
      failed_logins_total: 4,
      unique_users_logged_in_7d: 8,
    },
    documents: {
      total_documents: 24,
      total_storage_bytes: 52428800, // 50 MB
      total_storage_mb: 50.0,
      average_storage_per_user_mb: 4.17,
      failed_documents: 0,
      uploaded_today: 3,
      uploaded_this_month: 24,
    },
    ai_usage: {
      total_requests: 120,
      requests_today: 15,
      requests_this_month: 120,
      total_prompt_tokens: 35000,
      total_response_tokens: 28000,
      total_tokens: 63000,
      failed_requests: 1,
      estimated_cost_usd: 0.0315,
      models: [
        { model_name: 'gemini-2.5-flash', request_count: 100, total_tokens: 50000 },
        { model_name: 'gemini-2.5-pro', request_count: 20, total_tokens: 13000 },
      ],
    },
    server_time: '2026-11-05T10:00:00Z',
  };

  const mockHealth = {
    status: 'healthy',
    environment: 'development',
    version: '1.0.0',
    database: {
      healthy: true,
      dialect: 'postgresql',
      pgvector_ready: true,
    },
    storage: {
      provider: 's3',
      user_quota_mb: 500,
      ready: true,
    },
    ingestion: {
      durable_worker_enabled: true,
      concurrency: 2,
      status: 'active',
    },
    gemini: {
      model: 'gemini-2.5-flash',
      api_key_configured: true,
      rpm_limit: 60,
      status: 'ready',
    },
    timestamp: '2026-11-05T10:00:00Z',
  };

  const mockUsers = {
    users: [
      {
        id: 'usr_001',
        email: 'dr.curie@radium.org',
        display_name: 'Dr. Marie Curie',
        institution: 'Sorbonne',
        status: 'active',
        is_active: true,
        role: 'authenticated',
        created_at: '2026-10-15T08:00:00Z',
        last_login_at: '2026-11-05T09:30:00Z',
        login_count: 14,
        document_count: 5,
        storage_used_bytes: 25000000,
        storage_used_mb: 23.84,
        storage_quota_mb: 500,
        ai_request_count: 28,
        ai_total_tokens: 15400,
      },
    ],
    total: 1,
    page: 1,
    page_size: 15,
    total_pages: 1,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.getAdminOverview as any).mockResolvedValue(mockOverview);
    (api.getAdminSystemHealth as any).mockResolvedValue(mockHealth);
    (api.getAdminRegistrationAnalytics as any).mockResolvedValue([
      { date: '2026-11-01', count: 1 },
      { date: '2026-11-02', count: 2 },
    ]);
    (api.getAdminLoginAnalytics as any).mockResolvedValue([
      { date: '2026-11-01', success_count: 5, failure_count: 0 },
      { date: '2026-11-02', success_count: 8, failure_count: 1 },
    ]);
    (api.getAdminAIUsageAnalytics as any).mockResolvedValue([
      { date: '2026-11-01', requests: 10, tokens: 4000, estimated_cost_usd: 0.002 },
      { date: '2026-11-02', requests: 15, tokens: 6000, estimated_cost_usd: 0.003 },
    ]);
    (api.getAdminUsers as any).mockResolvedValue(mockUsers);
    (api.getAdminUserDetail as any).mockResolvedValue({
      user: mockUsers.users[0],
      recent_logins: [],
      recent_documents: [],
      active_sessions_count: 1,
      recent_sessions: [],
    });
    (api.getAdminUserActivity as any).mockResolvedValue([]);
  });

  it('renders executive overview metrics with correct values', async () => {
    render(<AdminDashboardView />);

    await waitFor(() => {
      expect(screen.getByText('Administrator Oversight Console')).toBeDefined();
    });

    expect(screen.getByText('Registered Researchers')).toBeDefined();
    expect(screen.getByText('12')).toBeDefined(); // total users
    expect(screen.getByText('48')).toBeDefined(); // total logins
    expect(screen.getByText('50.0')).toBeDefined(); // storage MB
    expect(screen.getByText('120')).toBeDefined(); // AI calls
  });

  it('switches to Researcher Directory and displays user data with 500 MB quota', async () => {
    render(<AdminDashboardView />);

    await waitFor(() => {
      expect(screen.getByText('Administrator Oversight Console')).toBeDefined();
    });

    const researchersTab = screen.getByRole('button', { name: /Researcher Directory/i });
    fireEvent.click(researchersTab);

    await waitFor(() => {
      expect(screen.getByText('Dr. Marie Curie')).toBeDefined();
      expect(screen.getByText('dr.curie@radium.org')).toBeDefined();
    });

    expect(screen.getByText('23.8 MB')).toBeDefined();
    expect(screen.getByRole('button', { name: 'Inspect' })).toBeDefined();
  });

  it('switches to Infrastructure & Health tab and displays readiness', async () => {
    render(<AdminDashboardView />);

    await waitFor(() => {
      expect(screen.getByText('Administrator Oversight Console')).toBeDefined();
    });

    const healthTab = screen.getByRole('button', { name: /Infrastructure & Health/i });
    fireEvent.click(healthTab);

    await waitFor(() => {
      expect(screen.getByText('FastAPI Application Backend')).toBeDefined();
      expect(screen.getByText('PostgreSQL / SQLite Persistence')).toBeDefined();
      expect(screen.getByText('Object Storage Abstraction')).toBeDefined();
      expect(screen.getByText('Google Gemini LLM Integration')).toBeDefined();
    });

    expect(screen.getByText('Key Securely Mounted (Never Exposed)')).toBeDefined();
  });

  it('opens AdminUserDetailModal on Inspect click and displays quota cards and tabs', async () => {
    render(<AdminDashboardView />);

    await waitFor(() => {
      expect(screen.getByText('Administrator Oversight Console')).toBeDefined();
    });

    const researchersTab = screen.getByRole('button', { name: /Researcher Directory/i });
    fireEvent.click(researchersTab);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Inspect' })).toBeDefined();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Inspect' }));

    // Modal dialog must be rendered with accessible role
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeDefined();
      expect(screen.getByText('Cumulative Storage Quota (500 MB Standard)')).toBeDefined();
      expect(screen.getByText('23.84 MB / 500 MB (5%)')).toBeDefined();
    });

    // Test tab navigation
    const docsTab = screen.getByRole('button', { name: /Documents/i });
    fireEvent.click(docsTab);
    expect(screen.getByText('Indexed Research Literature')).toBeDefined();

    const loginsTab = screen.getByRole('button', { name: /Login Audits/i });
    fireEvent.click(loginsTab);
    expect(screen.getByText('Recent Authentication Audit Events')).toBeDefined();

    const activityTab = screen.getByRole('button', { name: /Unified Activity Feed/i });
    fireEvent.click(activityTab);
    expect(screen.getByText('Chronological Researcher Activity')).toBeDefined();

    // Test close button
    const closeBtn = screen.getByRole('button', { name: 'Close' });
    fireEvent.click(closeBtn);

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).toBeNull();
    });
  }, 15000);

  it('closes AdminUserDetailModal on Escape key press', async () => {
    render(<AdminDashboardView />);

    await waitFor(() => {
      expect(screen.getByText('Administrator Oversight Console')).toBeDefined();
    });

    const researchersTab = screen.getByRole('button', { name: /Researcher Directory/i });
    fireEvent.click(researchersTab);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Inspect' })).toBeDefined();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Inspect' }));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeDefined();
    });

    fireEvent.keyDown(window, { key: 'Escape' });

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).toBeNull();
    });
  }, 15000);
});
