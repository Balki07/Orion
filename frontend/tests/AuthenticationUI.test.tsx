import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import App from '../src/App';
import { AuthHero } from '../src/features/auth/AuthHero';
import { AuthProvider } from '../src/context/AuthContext';
import { api } from '../src/services/api';

describe('Authentication UI Integration Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders AuthHero with particle sphere, branding, and sign-in form', () => {
    render(
      <AuthProvider>
        <AuthHero />
      </AuthProvider>
    );

    expect(screen.getByText('ORION')).toBeDefined();
    expect(screen.getByText('SECURE ACCESS')).toBeDefined();
    expect(screen.getByText('Enter your orbit')).toBeDefined();
    expect(screen.getByRole('tab', { name: 'Sign in' })).toBeDefined();
    expect(screen.getByRole('tab', { name: 'Create account' })).toBeDefined();
    expect(screen.getByLabelText(/Email address/i)).toBeDefined();
    expect(screen.getByLabelText(/^Password$/i)).toBeDefined();
    expect(screen.getByRole('button', { name: /Sign in to ORION/i })).toBeDefined();
  });

  it('switches between Sign in and Create account tabs', async () => {
    render(
      <AuthProvider>
        <AuthHero />
      </AuthProvider>
    );

    const createTab = screen.getByRole('tab', { name: 'Create account' });
    fireEvent.click(createTab);

    await waitFor(() => {
      expect(screen.getByText('Create your account')).toBeDefined();
      expect(screen.getByLabelText(/Full name/i)).toBeDefined();
      expect(screen.getByLabelText(/Confirm password/i)).toBeDefined();
      expect(screen.getByRole('button', { name: /Create account/i })).toBeDefined();
    });

    const signInTab = screen.getByRole('tab', { name: 'Sign in' });
    fireEvent.click(signInTab);

    await waitFor(() => {
      expect(screen.getByText('Enter your orbit')).toBeDefined();
    });
  });

  it('validates required fields and password strength on registration', async () => {
    render(
      <AuthProvider>
        <AuthHero />
      </AuthProvider>
    );

    // Switch to register tab
    fireEvent.click(screen.getByRole('tab', { name: 'Create account' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Create account/i })).toBeDefined();
    });

    const submitBtn = screen.getByRole('button', { name: /Create account/i });
    fireEvent.click(submitBtn);

    // Field errors must appear
    await waitFor(() => {
      expect(screen.getByText('Enter your full name.')).toBeDefined();
      expect(screen.getByText('Enter your email address.')).toBeDefined();
      expect(screen.getByText('Enter your password.')).toBeDefined();
    });

    // Test password strength validation (e.g. weak password)
    const passwordInput = screen.getByLabelText(/^Password/i, { selector: 'input' });
    fireEvent.change(passwordInput, { target: { value: 'weakpass' } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('Include at least one uppercase letter.')).toBeDefined();
    });
  });

  it('toggles password visibility when eye button is clicked', () => {
    render(
      <AuthProvider>
        <AuthHero />
      </AuthProvider>
    );

    const passwordInput = screen.getByLabelText(/^Password$/i) as HTMLInputElement;
    expect(passwordInput.type).toBe('password');

    const toggleBtn = screen.getByLabelText('Show password');
    fireEvent.click(toggleBtn);
    expect(passwordInput.type).toBe('text');

    fireEvent.click(screen.getByLabelText('Hide password'));
    expect(passwordInput.type).toBe('password');
  });

  it('submits login credentials to api.login and handles error response', async () => {
    vi.spyOn(api, 'login').mockRejectedValue(new Error('Invalid email or password.'));

    render(
      <AuthProvider>
        <AuthHero />
      </AuthProvider>
    );

    const emailInput = screen.getByLabelText(/Email address/i);
    const passwordInput = screen.getByLabelText(/^Password$/i);

    fireEvent.change(emailInput, { target: { value: 'researcher@oxford.ac.uk' } });
    fireEvent.change(passwordInput, { target: { value: 'WrongPassword!2026' } });

    const submitBtn = screen.getByRole('button', { name: /Sign in to ORION/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('Invalid email or password.')).toBeDefined();
    });
  });

  it('submits valid registration and establishes authenticated session', async () => {
    vi.spyOn(api, 'register').mockResolvedValue({
      user: {
        id: 'usr_123',
        email: 'new.researcher@cam.ac.uk',
        role: 'authenticated',
        display_name: 'Dr. New Researcher',
      },
      access_token: 'fake-jwt-token',
      token_type: 'bearer',
      expires_in: 3600,
      csrf_token: 'fake-csrf',
    });

    render(
      <AuthProvider>
        <AuthHero />
      </AuthProvider>
    );

    fireEvent.click(screen.getByRole('tab', { name: 'Create account' }));

    await waitFor(() => {
      expect(screen.getByLabelText(/Full name/i)).toBeDefined();
    });

    fireEvent.change(screen.getByLabelText(/Full name/i), { target: { value: 'Dr. New Researcher' } });
    fireEvent.change(screen.getByLabelText(/Email address/i), { target: { value: 'new.researcher@cam.ac.uk' } });
    fireEvent.change(screen.getByLabelText(/^Password$/i), { target: { value: 'ValidPass!2026' } });
    fireEvent.change(screen.getByLabelText(/Confirm password/i), { target: { value: 'ValidPass!2026' } });
    const termsCheckbox = screen.getByRole('checkbox');
    fireEvent.click(termsCheckbox);

    fireEvent.click(screen.getByRole('button', { name: /Create account/i }));

    await waitFor(() => {
      expect(api.register).toHaveBeenCalledWith({
        display_name: 'Dr. New Researcher',
        email: 'new.researcher@cam.ac.uk',
        password: 'ValidPass!2026',
        institution: null,
      });
    });
  });

  it('renders AuthHero when App opens without session, and transitions upon login', async () => {
    // 1. Initial /me call fails (unauthenticated)
    vi.spyOn(api, 'getMe').mockRejectedValue(new Error('Unauthenticated'));
    vi.spyOn(api, 'listDocuments').mockResolvedValue({ total: 0, items: [] });
    vi.spyOn(api, 'getUsage').mockResolvedValue({
      user_id: 'usr_new',
      document_count: 0,
      completed_document_count: 0,
      total_pages_ingested: 0,
      total_chunks_indexed: 0,
      note_count: 0,
      total_storage_bytes: 0,
    });
    vi.spyOn(api, 'listNotes').mockResolvedValue({ total: 0, items: [] });

    render(<App />);

    // Must show AuthHero
    await waitFor(() => {
      expect(screen.getByText('Enter your orbit')).toBeDefined();
    });

    // 2. Perform successful login
    vi.spyOn(api, 'login').mockResolvedValue({
      user: {
        id: 'usr_test_success',
        email: 'verified@orion.ai',
        role: 'authenticated',
        display_name: 'Verified User',
      },
      access_token: 'fake-jwt',
      token_type: 'bearer',
      expires_in: 3600,
      csrf_token: 'fake-csrf',
    });

    fireEvent.change(screen.getByLabelText(/Email address/i), { target: { value: 'verified@orion.ai' } });
    fireEvent.change(screen.getByLabelText(/^Password$/i), { target: { value: 'ValidPass!2026' } });
    fireEvent.click(screen.getByRole('button', { name: /Sign in to ORION/i }));

    await waitFor(() => {
      expect(api.login).toHaveBeenCalledWith({
        email: 'verified@orion.ai',
        password: 'ValidPass!2026',
      });
    });

    // User transitions into main ORION app
    await waitFor(() => {
      expect(screen.getByLabelText('Sign out')).toBeDefined();
    });
  });

  it('renders Option A Public Evaluation gateway with warm gold styling and triggers onEnterDemo', () => {
    const onEnterDemoMock = vi.fn();
    render(
      <AuthProvider>
        <AuthHero onEnterDemo={onEnterDemoMock} />
      </AuthProvider>
    );

    // Option A Header & Badge
    const optionA = screen.getByText('Option A • Public Evaluation');
    expect(optionA).toBeDefined();
    expect(optionA.className).toContain('text-[#ffb84c]');

    expect(screen.getByText('No Login Required')).toBeDefined();
    expect(screen.getByRole('heading', { name: /Explore Public Demo/i })).toBeDefined();

    // Launch button with gold gradient and charcoal text
    const launchBtn = screen.getByRole('button', { name: /Launch Public Demo Workspace/i });
    expect(launchBtn).toBeDefined();
    expect(launchBtn.className).toContain('from-[#ffb84c]');
    expect(launchBtn.className).toContain('to-[#e59a27]');
    expect(launchBtn.className).toContain('text-[#17130f]');

    // Click triggers onEnterDemo callback
    fireEvent.click(launchBtn);
    expect(onEnterDemoMock).toHaveBeenCalledTimes(1);
  });
});
