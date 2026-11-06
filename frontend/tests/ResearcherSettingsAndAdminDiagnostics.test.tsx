import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { SettingsView } from '../src/features/settings/SettingsView';
import { AdminSystemDiagnosticsView } from '../src/features/admin/AdminSystemDiagnosticsView';
import App from '../src/App';
import { AuthProvider } from '../src/context/AuthContext';
import { api } from '../src/services/api';
import { User, UserUsage, StorageUsageResponse, SystemSettings, AdminSystemHealth, AdminOverviewResponse } from '../src/types';

describe('Researcher Settings & Admin System Diagnostics Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.location.hash = '';
    window.history.replaceState({}, '', '/');
    localStorage.clear();
  });

  const mockResearcher: User = {
    id: 'usr_secret_tenant_999',
    email: 'scholar@oxford.ac.uk',
    display_name: 'Dr. Jane Scholar',
    institution: 'University of Oxford',
    role: 'authenticated',
    status: 'active',
    is_active: true,
    created_at: '2026-10-15T12:00:00Z',
  };

  const mockAdmin: User = {
    id: 'usr_admin_001',
    email: 'orionadmin@gmail.com',
    display_name: 'ORION Administrator',
    role: 'admin',
    status: 'active',
    is_active: true,
    created_at: '2026-10-01T08:00:00Z',
  };

  const mockUsage: UserUsage = {
    user_id: 'usr_secret_tenant_999',
    document_count: 6,
    completed_document_count: 6,
    total_pages_ingested: 84,
    total_chunks_indexed: 312,
    total_storage_bytes: 41943040, // 40 MB
    storage_mb_used: 40.0,
    storage_quota_mb: 500,
    storage_pct_used: 8.0,
    llm_tokens_consumed: 35000,
    llm_prompt_tokens: 22000,
    llm_completion_tokens: 13000,
    llm_queries_executed: 42,
    collection_count: 2,
    session_count: 5,
    note_count: 4,
  };

  const mockStorageUsage: StorageUsageResponse = {
    user_id: 'usr_secret_tenant_999',
    total_documents: 6,
    total_storage_bytes: 41943040,
    total_storage_mb: 40.0,
    storage_quota_mb: 500.0,
    quota_usage_percent: 8.0,
    remaining_storage_mb: 460.0,
    quota_exceeded: false,
    quota_warning: false,
  };

  const mockSystemSettings: SystemSettings = {
    app_name: 'ORION',
    app_version: '1.0.0',
    environment: 'staging',
    active_gemini_model: 'gemini-2.5-flash',
    active_embedding_model: 'BAAI/bge-small-en-v1.5',
    embedding_dimensions: 384,
    storage_provider: 's3',
    max_upload_size_mb: 32,
    max_pdf_pages: 200,
    chunk_size: 500,
    chunk_overlap: 80,
    retrieval_top_k: 8,
    hybrid_fusion_alpha: 0.6,
    reranker_enabled: false,
  };

  const mockSystemHealth: AdminSystemHealth = {
    status: 'healthy',
    environment: 'staging',
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
    timestamp: '2026-11-05T12:00:00Z',
  };

  const mockOverview: AdminOverviewResponse = {
    users: {
      total_users: 15,
      active_users_24h: 5,
      active_users_7d: 11,
      active_users_30d: 15,
      new_users_today: 1,
      new_users_this_week: 4,
      new_users_this_month: 15,
    },
    logins: {
      total_logins: 92,
      logins_today: 14,
      logins_this_week: 55,
      failed_logins_today: 0,
      failed_logins_total: 3,
      unique_users_logged_in_7d: 11,
    },
    documents: {
      total_documents: 48,
      total_storage_bytes: 104857600,
      total_storage_mb: 100.0,
      average_storage_per_user_mb: 6.67,
      failed_documents: 0,
      uploaded_today: 4,
      uploaded_this_month: 48,
    },
    ai_usage: {
      total_requests: 210,
      requests_today: 28,
      requests_this_month: 210,
      total_prompt_tokens: 65000,
      total_response_tokens: 45000,
      total_tokens: 110000,
      failed_requests: 1,
      estimated_cost_usd: 0.055,
      models: [
        { model_name: 'gemini-2.5-flash', request_count: 210, total_tokens: 110000 },
      ],
    },
    server_time: '2026-11-05T12:00:00Z',
  };

  const mockSessions = [
    {
      id: 'sess_1',
      ip_address: '192.168.1.10',
      user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
      created_at: '2026-11-05T10:00:00Z',
      expires_at: '2026-11-06T10:00:00Z',
      is_active: true,
      is_current: true,
    },
    {
      id: 'sess_2',
      ip_address: '10.0.0.5',
      user_agent: 'Mobile Safari',
      created_at: '2026-11-04T15:00:00Z',
      expires_at: '2026-11-05T15:00:00Z',
      is_active: true,
      is_current: false,
    },
  ];

  it('renders Researcher Settings with all 5 sections and does not expose tenant id', async () => {
    vi.spyOn(api, 'getMe').mockResolvedValue(mockResearcher);
    vi.spyOn(api, 'getUsage').mockResolvedValue(mockUsage);
    vi.spyOn(api, 'getStorageUsage').mockResolvedValue(mockStorageUsage);
    vi.spyOn(api, 'getSettings').mockResolvedValue(mockSystemSettings);
    vi.spyOn(api, 'listAuthSessions').mockResolvedValue(mockSessions);

    render(
      <AuthProvider>
        <SettingsView />
      </AuthProvider>
    );

    // Section 1: Account & Profile
    await waitFor(() => {
      expect(screen.getByText('Settings')).toBeDefined();
      expect(screen.getByText('Researcher Identity')).toBeDefined();
      expect(screen.getByDisplayValue('Dr. Jane Scholar')).toBeDefined();
      expect(screen.getByDisplayValue('scholar@oxford.ac.uk')).toBeDefined();
    });

    // Tenant ID must NOT be exposed
    expect(screen.queryByText('usr_secret_tenant_999')).toBeNull();
    expect(screen.queryByText(/Tenant ID/i)).toBeNull();

    // Section 2: Switch to Security & Privacy
    const secBtn = screen.getByRole('button', { name: /Security & Privacy/i });
    fireEvent.click(secBtn);

    await waitFor(() => {
      expect(screen.getByText('Change Password')).toBeDefined();
      expect(screen.getByText('Active Login Sessions')).toBeDefined();
      expect(screen.getByText('Privacy & Document Isolation')).toBeDefined();
      expect(screen.getByText('Current Session')).toBeDefined();
    });

    // Section 3: Switch to Storage & Uploads
    const storageBtn = screen.getByRole('button', { name: /Storage & Uploads/i });
    fireEvent.click(storageBtn);

    await waitFor(() => {
      expect(screen.getByText('Storage & Upload Allocation')).toBeDefined();
      expect(screen.getByText('40.00 MB / 500 MB (8%)')).toBeDefined();
      expect(screen.getByText('460.00 MB remaining')).toBeDefined();
      expect(screen.getByText('32 MB')).toBeDefined(); // Max Upload
    });

    // Section 4: Switch to Research Preferences
    const prefsBtn = screen.getByRole('button', { name: /Research Preferences/i });
    fireEvent.click(prefsBtn);

    await waitFor(() => {
      expect(screen.getByText('Scholarly Research Preferences')).toBeDefined();
      expect(screen.getByText('Preferred Answer Style')).toBeDefined();
      expect(screen.getByText('Comprehensive Scholarly')).toBeDefined();
      expect(screen.getByText('Default Retrieval Depth (Top-K Passages)')).toBeDefined();
    });

    // Section 5: Switch to Usage & Activity
    const activityBtn = screen.getByRole('button', { name: /Usage & Activity/i });
    fireEvent.click(activityBtn);

    await waitFor(() => {
      expect(screen.getByText('Workspace Usage & Activity Metrics')).toBeDefined();
      expect(screen.getByText('42')).toBeDefined(); // AI queries
      expect(screen.getByText('35,000')).toBeDefined(); // token volume
    });
  });

  it('supports functional password change and session revocation in Researcher Settings', async () => {
    vi.spyOn(api, 'getMe').mockResolvedValue(mockResearcher);
    vi.spyOn(api, 'getUsage').mockResolvedValue(mockUsage);
    vi.spyOn(api, 'getStorageUsage').mockResolvedValue(mockStorageUsage);
    vi.spyOn(api, 'getSettings').mockResolvedValue(mockSystemSettings);
    vi.spyOn(api, 'listAuthSessions').mockResolvedValue(mockSessions);
    const changePasswordSpy = vi.spyOn(api, 'changePassword').mockResolvedValue({ message: 'Password changed successfully.' });
    const revokeSpy = vi.spyOn(api, 'revokeOtherSessions').mockResolvedValue({ message: 'All other sessions revoked.' });

    render(
      <AuthProvider>
        <SettingsView />
      </AuthProvider>
    );

    const secBtn = screen.getByRole('button', { name: /Security & Privacy/i });
    fireEvent.click(secBtn);

    await waitFor(() => {
      expect(screen.getByText('Change Password')).toBeDefined();
    });

    // Fill password form using explicit aria-labels
    const currentPassInput = screen.getByLabelText('Current Password');
    const newPassInput = screen.getByLabelText('New Password');
    const confirmPassInput = screen.getByLabelText('Confirm New Password');

    fireEvent.change(currentPassInput, { target: { value: 'OldPassword123!' } });
    fireEvent.change(newPassInput, { target: { value: 'NewSecurePass456!' } });
    fireEvent.change(confirmPassInput, { target: { value: 'NewSecurePass456!' } });

    const updateBtn = screen.getByRole('button', { name: /Update Password/i });
    fireEvent.click(updateBtn);

    await waitFor(() => {
      expect(changePasswordSpy).toHaveBeenCalledWith('OldPassword123!', 'NewSecurePass456!');
      expect(screen.getByText('Password changed successfully.')).toBeDefined();
    });

    // Revoke other sessions
    const revokeBtn = screen.getByRole('button', { name: /Revoke Other Sessions/i });
    fireEvent.click(revokeBtn);

    await waitFor(() => {
      expect(revokeSpy).toHaveBeenCalled();
      expect(screen.getByText('All other active sessions have been revoked.')).toBeDefined();
    });
  });

  it('renders Admin System Diagnostics with technical configuration and system metrics', async () => {
    vi.spyOn(api, 'getSettings').mockResolvedValue(mockSystemSettings);
    vi.spyOn(api, 'getAdminSystemHealth').mockResolvedValue(mockSystemHealth);
    vi.spyOn(api, 'getAdminOverview').mockResolvedValue(mockOverview);

    render(<AdminSystemDiagnosticsView />);

    await waitFor(() => {
      expect(screen.getByText('System Diagnostics & Technical Architecture')).toBeDefined();
      expect(screen.getByText('FastAPI Application Backend')).toBeDefined();
      expect(screen.getByText('Google Gemini LLM Integration')).toBeDefined();
      expect(screen.getByText('Embedding Model & Vectors')).toBeDefined();
      expect(screen.getByText('Retrieval Top-K & RRF Fusion')).toBeDefined();
      expect(screen.getByText('Chunking & Ingestion Pipeline')).toBeDefined();
      expect(screen.getByText('Cross-Encoder Configuration')).toBeDefined();
      expect(screen.getByText('PostgreSQL / SQLite Persistence')).toBeDefined();
      expect(screen.getByText('Object Storage Abstraction')).toBeDefined();
      expect(screen.getByText('Durable Ingestion Worker')).toBeDefined();
      expect(screen.getByText('Authentication & Security')).toBeDefined();
      expect(screen.getByText('System-Wide Metrics & Operational Telemetry')).toBeDefined();
      expect(screen.getByText((110000).toLocaleString())).toBeDefined(); // Token volume
      expect(screen.getByText('15')).toBeDefined(); // Total registered
    });
  });

  it('restricts direct route access to #diagnostics by role', async () => {
    window.location.hash = '#diagnostics';

    // 1. Regular researcher is blocked with Access Restricted
    vi.spyOn(api, 'getMe').mockResolvedValue(mockResearcher);
    vi.spyOn(api, 'listDocuments').mockResolvedValue({ total: 0, items: [] });
    vi.spyOn(api, 'getUsage').mockResolvedValue(mockUsage);

    const { unmount } = render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Access Restricted')).toBeDefined();
      expect(
        screen.getByText(/Administrative privileges are required to access System Diagnostics/i)
      ).toBeDefined();
    });

    unmount();

    // 2. Administrator is granted access to System Diagnostics
    window.location.hash = '#diagnostics';
    vi.spyOn(api, 'getMe').mockResolvedValue(mockAdmin);
    vi.spyOn(api, 'getSettings').mockResolvedValue(mockSystemSettings);
    vi.spyOn(api, 'getAdminSystemHealth').mockResolvedValue(mockSystemHealth);
    vi.spyOn(api, 'getAdminOverview').mockResolvedValue(mockOverview);

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('System Diagnostics & Technical Architecture')).toBeDefined();
      expect(screen.getByText('FastAPI Application Backend')).toBeDefined();
    });
  });
});
