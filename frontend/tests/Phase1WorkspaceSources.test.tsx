import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { SourcesPanel } from '../src/features/research/SourcesPanel';
import { ScopeGuardPrompt } from '../src/features/research/ScopeGuardPrompt';
import { DocumentItem } from '../src/types';

const mockDocs: DocumentItem[] = [
  {
    id: '1',
    title: 'EPR In India: Status and Prospects',
    filename: 'Somantri.pdf',
    total_chunks: 12,
    file_size_bytes: 409600,
    page_count: 14,
    content_hash: 'hash-abc-123',
    uploaded_at: '2026-03-01T10:00:00Z',
  },
  {
    id: '2',
    title: 'EPR In India: Duplicate Copy',
    filename: 'isi_31.07_22.pdf',
    total_chunks: 12,
    file_size_bytes: 409600,
    page_count: 14,
    content_hash: 'hash-abc-123', // Same content_hash as id '1'
    uploaded_at: '2026-03-02T10:00:00Z',
  },
  {
    id: '3',
    title: 'Plastic Waste Rules Framework',
    filename: 'Plastic_Waste_2024.pdf',
    total_chunks: 8,
    file_size_bytes: 204800,
    page_count: 8,
    content_hash: 'hash-xyz-789',
    uploaded_at: '2026-03-03T10:00:00Z',
  },
];

describe('Phase 1 SourcesPanel & Duplicate Management', () => {
  it('detects duplicate documents and shows "Same file as" badge', () => {
    const handleToggle = vi.fn();
    const handleSelectAll = vi.fn();

    render(
      <SourcesPanel
        documents={mockDocs}
        selectedDocIds={['1', '2', '3']}
        onToggleDoc={handleToggle}
        onSelectAll={handleSelectAll}
      />
    );

    // Document 2 is a duplicate of Document 1
    expect(screen.getByText(/Same file as/i)).toBeDefined();
    expect(screen.getAllByText('Somantri.pdf').length).toBe(2);
    expect(screen.getByText(/Deselect copy/i)).toBeDefined();
  });

  it('clicking "Deselect copy" toggles off the duplicate document', () => {
    const handleToggle = vi.fn();
    const handleDeselect = vi.fn();

    render(
      <SourcesPanel
        documents={mockDocs}
        selectedDocIds={['1', '2', '3']}
        onToggleDoc={handleToggle}
        onSelectAll={vi.fn()}
        onDeselectDoc={handleDeselect}
      />
    );

    const deselectBtn = screen.getByText(/Deselect copy/i);
    fireEvent.click(deselectBtn);

    expect(handleDeselect).toHaveBeenCalledWith('2');
  });

  it('filters source documents in real-time via search input', () => {
    render(
      <SourcesPanel
        documents={mockDocs}
        selectedDocIds={['1', '2', '3']}
        onToggleDoc={vi.fn()}
        onSelectAll={vi.fn()}
      />
    );

    const searchInput = screen.getByPlaceholderText(/Filter papers by title\.\.\./i);
    fireEvent.change(searchInput, { target: { value: 'Plastic' } });

    // "Plastic_Waste_2024.pdf" should be visible
    expect(screen.getByText('Plastic_Waste_2024.pdf')).toBeDefined();
    // Somantri should be filtered out
    expect(screen.queryByText('Somantri.pdf')).toBeNull();
  });
});

describe('Phase 1 ScopeGuardPrompt', () => {
  it('renders "Which paper?" when query contains ambiguous singular reference and multiple docs selected', () => {
    const handleSelectSingle = vi.fn();
    const handleContinueAll = vi.fn();

    render(
      <ScopeGuardPrompt
        question="What methodology does this paper propose for EPR?"
        selectedDocuments={mockDocs}
        onSelectSingleDoc={handleSelectSingle}
        onContinueAll={handleContinueAll}
      />
    );

    expect(screen.getByText(/Which paper\?/i)).toBeDefined();
    expect(screen.getByText(/Your question refers to a specific paper/i)).toBeDefined();

    // Clicking a paper chip narrows the scope
    const somantriChip = screen.getByText('Somantri.pdf');
    fireEvent.click(somantriChip);
    expect(handleSelectSingle).toHaveBeenCalledWith('1');
  });

  it('allows user to bypass and continue with all selected documents', () => {
    const handleSelectSingle = vi.fn();
    const handleContinueAll = vi.fn();

    render(
      <ScopeGuardPrompt
        question="Summarize this study"
        selectedDocuments={mockDocs}
        onSelectSingleDoc={handleSelectSingle}
        onContinueAll={handleContinueAll}
      />
    );

    const continueBtn = screen.getByText(/Continue with all/i);
    fireEvent.click(continueBtn);
    expect(handleContinueAll).toHaveBeenCalledTimes(1);
  });

  it('does not render when only one document is selected', () => {
    const { container } = render(
      <ScopeGuardPrompt
        question="What does this study find?"
        selectedDocuments={[mockDocs[0]]}
        onSelectSingleDoc={vi.fn()}
        onContinueAll={vi.fn()}
      />
    );

    expect(container.firstChild).toBeNull();
  });
});
