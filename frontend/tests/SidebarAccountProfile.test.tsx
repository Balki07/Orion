import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { Sidebar } from '../src/components/layout/Sidebar';
import { AuthProvider, useAuth } from '../src/context/AuthContext';
import { api } from '../src/services/api';
import { User } from '../src/types';

// Mock child AuthContext consumer for controlled testing
const SidebarWithMockUser: React.FC<{ mockUser: User | null; onSignOutMock?: () => void }> = ({
  mockUser,
  onSignOutMock,
}) => {
  return (
    <Sidebar
      currentTab="dashboard"
      onSelectTab={vi.fn()}
      onOpenUpload={vi.fn()}
      isOpen={true}
    />
  );
};

describe('Sidebar Production Account Section & Development Cleanup', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders clean account profile with user display name, email, initials avatar, and sign out button', () => {
    const mockUser: User = {
      id: 'usr_real_7a8b9c0d',
      email: 'dr.curie@radium.ac.fr',
      display_name: 'Dr. Marie Curie',
      institution: 'Sorbonne University',
      role: 'authenticated',
    };

    vi.spyOn(api, 'getMe').mockResolvedValue(mockUser);

    // Render with AuthContext initialized with mockUser
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

    // Must NOT contain development tenant indicators
    expect(screen.queryByText(/LOCAL VERIFIED MODE/i)).toBeNull();
    expect(screen.queryByText(/Test Tenant/i)).toBeNull();
    expect(screen.queryByRole('button', { name: /^User A$/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /^User B$/i })).toBeNull();
    expect(screen.queryByText(/ID: usr_real_7a8b9c0d/i)).toBeNull();
    expect(screen.queryByText(/user_dev_researcher/i)).toBeNull();

    // Must contain Sign Out button
    expect(screen.getAllByRole('button', { name: /Sign out/i })[0]).toBeDefined();
  });

  it('falls back to email address when display_name is not set', async () => {
    const mockUserWithoutName: User = {
      id: 'usr_real_12345678',
      email: 'solo.researcher@institute.org',
      display_name: null,
      institution: 'Global Institute',
      role: 'authenticated',
    };

    vi.spyOn(api, 'getMe').mockResolvedValue(mockUserWithoutName);

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

    // Verify development indicators remain absent
    expect(screen.queryByText(/LOCAL VERIFIED MODE/i)).toBeNull();
    expect(screen.queryByText(/Test Tenant/i)).toBeNull();
    expect(screen.queryByText(/ID:/i)).toBeNull();
  });

  it('invokes signOut when sign out button is clicked', async () => {
    const logoutSpy = vi.spyOn(api, 'logout').mockResolvedValue({ message: 'Logged out successfully.' });

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

    const signOutButtons = screen.getAllByRole('button', { name: /Sign out/i });
    expect(signOutButtons.length).toBeGreaterThan(0);
    fireEvent.click(signOutButtons[0]);

    expect(logoutSpy).toHaveBeenCalled();
  });
});

