import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { Sidebar } from '../src/components/layout/Sidebar';
import { AuthProvider } from '../src/context/AuthContext';
import App from '../src/App';
import { api } from '../src/services/api';
import { User, UserUsage } from '../src/types';

describe('Admin Sidebar & Role Enforcement UI Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.location.hash = '';
    window.history.replaceState({}, '', '/');
  });

  const adminUser: User = {
    id: 'usr_admin_001',
    email: 'orionadmin@gmail.com',
    display_name: 'ORION Administrator',
    role: 'admin',
    status: 'active',
    is_active: true,
  };

  const regularUser: User = {
    id: 'usr_reg_001',
    email: 'researcher@oxford.ac.uk',
    display_name: 'Dr. Jane Doe',
    role: 'authenticated',
    status: 'active',
    is_active: true,
  };

  const mockUsage: UserUsage = {
    documents_uploaded: 3,
    storage_bytes_used: 12500000,
    storage_mb_used: 11.92,
    storage_quota_mb: 500,
    storage_pct_used: 2.38,
    llm_tokens_consumed: 12000,
    llm_prompt_tokens: 8000,
    llm_completion_tokens: 4000,
    llm_queries_executed: 15,
    user_id: 'usr_reg_001',
  };

  it('renders Admin Console and Design Tokens & UI in Sidebar when user has role: admin', async () => {
    vi.spyOn(api, 'getMe').mockResolvedValue(adminUser);

    render(
      <AuthProvider>
        <Sidebar
          currentTab="dashboard"
          onSelectTab={vi.fn()}
          onOpenUpload={vi.fn()}
          isOpen={true}
        />
      </AuthProvider>
    );

    // Both Admin Console and Design Tokens & UI must be present when user role is admin
    await waitFor(() => {
      const adminItems = screen.getAllByText('Admin Console');
      expect(adminItems.length).toBeGreaterThanOrEqual(1);

      const previewItems = screen.getAllByText('Design Tokens & UI');
      expect(previewItems.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('does NOT render Admin Console or Design Tokens & UI in Sidebar when user is ordinary researcher', async () => {
    vi.spyOn(api, 'getMe').mockResolvedValue(regularUser);

    render(
      <AuthProvider>
        <Sidebar
          currentTab="dashboard"
          onSelectTab={vi.fn()}
          onOpenUpload={vi.fn()}
          isOpen={true}
        />
      </AuthProvider>
    );

    // Verify user profile is rendered
    await waitFor(() => {
      const nameItems = screen.getAllByText('Dr. Jane Doe');
      expect(nameItems.length).toBeGreaterThanOrEqual(1);
    });

    // Neither Admin Console nor Design Tokens & UI must be present
    expect(screen.queryByText('Admin Console')).toBeNull();
    expect(screen.queryByText('Design Tokens & UI')).toBeNull();
  });

  it('blocks regular researcher direct access to #preview with Access Restricted and allows return to Dashboard', async () => {
    window.location.hash = '#preview';

    vi.spyOn(api, 'getMe').mockResolvedValue(regularUser);
    vi.spyOn(api, 'listDocuments').mockResolvedValue({ total: 0, items: [] });
    vi.spyOn(api, 'getUsage').mockResolvedValue(mockUsage);

    render(<App />);

    // Access Restricted banner must be rendered
    await waitFor(() => {
      expect(screen.getByText('Access Restricted')).toBeDefined();
      expect(
        screen.getByText(/Administrative privileges are required to access Design Tokens & UI/i)
      ).toBeDefined();
    });

    // Clicking "Return to Dashboard" must return user to Dashboard
    const returnBtn = screen.getByRole('button', { name: /return to dashboard/i });
    fireEvent.click(returnBtn);

    await waitFor(() => {
      expect(screen.getByText('Indexed Papers')).toBeDefined();
    });
  });

  it('allows administrator direct access to #preview and renders Design Tokens & UI', async () => {
    window.location.hash = '#preview';

    vi.spyOn(api, 'getMe').mockResolvedValue(adminUser);
    vi.spyOn(api, 'listDocuments').mockResolvedValue({ total: 0, items: [] });
    vi.spyOn(api, 'getUsage').mockResolvedValue(mockUsage);

    render(<App />);

    // Design Tokens preview component must be rendered
    await waitFor(() => {
      expect(screen.getByText('Design Tokens & Component Kit')).toBeDefined();
      expect(screen.getByText('The Reading Room')).toBeDefined();
    });
  });
});
