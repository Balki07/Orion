import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import App from '../src/App';
import { AuthProvider } from '../src/context/AuthContext';
import { Sidebar } from '../src/components/layout/Sidebar';
import { ResearchWorkspace } from '../src/features/research/ResearchWorkspace';
import { api } from '../src/services/api';

const mockDocuments = [
  {
    id: 'doc_1',
    user_id: 'user_dev_researcher_001',
    filename: 'attention_is_all_you_need.pdf',
    file_size: 2200000,
    page_count: 15,
    chunk_count: 48,
    status: 'completed' as const,
    created_at: '2026-10-19T10:00:00Z',
    updated_at: '2026-10-19T10:00:00Z',
  },
  {
    id: 'doc_2',
    user_id: 'user_dev_researcher_001',
    filename: 'retrieval_augmented_generation.pdf',
    file_size: 1800000,
    page_count: 12,
    chunk_count: 36,
    status: 'completed' as const,
    created_at: '2026-10-19T10:00:00Z',
    updated_at: '2026-10-19T10:00:00Z',
  },
];

describe('ORION Responsive Layout & Usability Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    vi.spyOn(api, 'listDocuments').mockResolvedValue({
      total: 2,
      items: mockDocuments,
    });
    vi.spyOn(api, 'getUsage').mockResolvedValue({
      user_id: 'user_dev_researcher_001',
      document_count: 2,
      completed_document_count: 2,
      total_pages_ingested: 27,
      total_chunks_indexed: 84,
      note_count: 1,
      total_storage_bytes: 4000000,
    });
    vi.spyOn(api, 'listNotes').mockResolvedValue({
      total: 0,
      items: [],
    });
    vi.spyOn(api, 'getMe').mockResolvedValue({
      id: 'user_dev_researcher_001',
      email: 'researcher@orion-assistant.ai',
      role: 'authenticated',
      display_name: 'Dr. Researcher',
      status: 'active',
      is_active: true,
    });
  });

  it('renders large desktop layout with permanent docked sidebar and panels', async () => {
    render(<App />);

    // Wait for initial dashboard data to resolve
    await waitFor(() => {
      expect(screen.getByText('Indexed Papers')).toBeDefined();
    });

    // Desktop docked sidebar is rendered
    const desktopSidebar = screen.getByRole('complementary', { name: /desktop main navigation/i });
    expect(desktopSidebar).toBeDefined();
    expect(desktopSidebar.className).toContain('hidden md:flex');
  });

  it('renders mobile navigation header with hamburger button', async () => {
    render(<App />);

    // Wait for initial dashboard data to resolve
    await waitFor(() => {
      expect(screen.getByText('Indexed Papers')).toBeDefined();
    });

    // Mobile header button exists with accessible aria label and controls
    const menuBtn = screen.getByRole('button', { name: /open navigation menu/i });
    expect(menuBtn).toBeDefined();
    expect(menuBtn.getAttribute('aria-expanded')).toBe('false');

    // Click hamburger button to open mobile navigation drawer
    fireEvent.click(menuBtn);
    expect(menuBtn.getAttribute('aria-expanded')).toBe('true');

    // Mobile drawer should now be visible
    const mobileDrawer = screen.getByRole('dialog', { name: /navigation sidebar/i });
    expect(mobileDrawer).toBeDefined();

    // Close button inside mobile drawer closes it
    const closeBtn = screen.getByRole('button', { name: /close navigation sidebar/i });
    fireEvent.click(closeBtn);

    expect(screen.queryByRole('dialog', { name: /navigation sidebar/i })).toBeNull();
  });

  it('supports Escape key to close the mobile navigation drawer', async () => {
    const handleClose = vi.fn();
    render(
      <AuthProvider>
        <Sidebar
          currentTab="research"
          onSelectTab={() => {}}
          onOpenUpload={() => {}}
          isOpen={true}
          onClose={handleClose}
        />
      </AuthProvider>
    );

    expect(screen.getByRole('dialog', { name: /navigation sidebar/i })).toBeDefined();

    // Press Escape
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('renders ResearchWorkspace with responsive drawer toggles and source counters', async () => {
    render(<ResearchWorkspace />);

    // Wait for documents to load
    await waitFor(() => {
      expect(api.listDocuments).toHaveBeenCalled();
    });

    // Check desktop docked panels exist
    expect(document.getElementById('desktop-sources-panel')).toBeDefined();
    expect(document.getElementById('desktop-citation-panel')).toBeDefined();

    // Check responsive toggle buttons exist with accessible attributes
    const sourcesToggle = screen.getByRole('button', { name: /toggle scope sources panel/i });
    const citationToggle = screen.getByRole('button', { name: /toggle citation evidence inspector/i });

    expect(sourcesToggle).toBeDefined();
    expect(sourcesToggle.getAttribute('aria-expanded')).toBe('false');
    expect(sourcesToggle.getAttribute('aria-controls')).toBe('sources-drawer');

    expect(citationToggle).toBeDefined();
    expect(citationToggle.getAttribute('aria-expanded')).toBe('false');
    expect(citationToggle.getAttribute('aria-controls')).toBe('citation-drawer');
  });

  it('opens and closes Scope Sources drawer on responsive viewports', async () => {
    render(<ResearchWorkspace />);

    await waitFor(() => {
      expect(api.listDocuments).toHaveBeenCalled();
    });

    const sourcesToggle = screen.getByRole('button', { name: /toggle scope sources panel/i });

    // Click toggle to open drawer
    fireEvent.click(sourcesToggle);
    expect(sourcesToggle.getAttribute('aria-expanded')).toBe('true');

    const sourcesDrawer = screen.getByRole('dialog', { name: /scope sources drawer/i });
    expect(sourcesDrawer).toBeDefined();

    // Close drawer using visible close button
    const closeBtn = screen.getByRole('button', { name: /close scope sources/i });
    fireEvent.click(closeBtn);

    expect(screen.queryByRole('dialog', { name: /scope sources drawer/i })).toBeNull();
  });

  it('supports source selection inside the responsive Scope Sources drawer', async () => {
    render(<ResearchWorkspace />);

    await waitFor(() => {
      expect(screen.getAllByText('attention_is_all_you_need.pdf').length).toBeGreaterThan(0);
    });

    // Open drawer
    const sourcesToggle = screen.getByRole('button', { name: /toggle scope sources panel/i });
    fireEvent.click(sourcesToggle);

    const sourcesDrawer = screen.getByRole('dialog', { name: /scope sources drawer/i });
    expect(sourcesDrawer).toBeDefined();

    // Click Deselect All inside the drawer
    const deselectBtn = screen.getAllByText('Deselect All')[1] || screen.getAllByText('Deselect All')[0];
    fireEvent.click(deselectBtn);

    // Verify Select All appears
    expect(screen.getAllByText('Select All').length).toBeGreaterThan(0);

    // Click Select All
    const selectAllBtn = screen.getAllByText('Select All')[0];
    fireEvent.click(selectAllBtn);
    expect(screen.getAllByText('Deselect All').length).toBeGreaterThan(0);
  });

  it('opens Citation Evidence Inspector drawer when a citation is clicked', async () => {
    // Spy on askQuestion to return a message with verified citations
    vi.spyOn(api, 'askQuestion').mockResolvedValue({
      answer: 'Self-attention allows connecting all positions with constant operations [cite:1].',
      claims: [
        {
          text: 'Self-attention connects all positions with constant operations',
          support_status: 'supported' as const,
          chunk_ids: ['chk_1'],
        },
      ],
      citations: [
        {
          citation_id: 'cite:1',
          document_id: 'doc_1',
          filename: 'attention_is_all_you_need.pdf',
          page_numbers: [6],
          chunk_ids: ['chk_1'],
          excerpt: 'Table 1: Maximum path lengths, per-layer complexity and minimum number of sequential operations.',
        },
      ],
      insufficient_evidence: false,
      warnings: [],
      latency_ms: { total: 420 },
      message_id: 'msg_test_1',
    });

    render(<ResearchWorkspace />);

    await waitFor(() => {
      expect(api.listDocuments).toHaveBeenCalled();
    });

    // Submit question
    const input = screen.getByPlaceholderText(/ask a technical or research question/i);
    fireEvent.change(input, { target: { value: 'What is self-attention complexity?' } });

    const submitBtn = screen.getByRole('button', { name: /verify/i });
    fireEvent.click(submitBtn);

    // Wait for answer and citation chip
    await waitFor(() => {
      expect(screen.getByText('[cite:1]')).toBeDefined();
    });

    // Click on the citation chip
    const chip = screen.getByText('[cite:1]');
    fireEvent.click(chip);

    // Citation drawer should be open
    const citationDrawer = screen.getByRole('dialog', { name: /citation evidence inspector drawer/i });
    expect(citationDrawer).toBeDefined();
    expect(screen.getAllByText('Citation Provenance Target').length).toBeGreaterThan(0);

    // Close with Escape key
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: /citation evidence inspector drawer/i })).toBeNull();
  });
});
