import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { StatusBadge } from '../src/components/common/StatusBadge';
import { CitationChip } from '../src/components/common/CitationChip';
import { OrionLogo } from '../src/components/icons/OrionLogo';

describe('ORION Frontend Component Tests', () => {
  it('renders official ORION brand logo and wordmark', () => {
    render(<OrionLogo showWordmark={true} />);
    expect(screen.getByText('ORION')).toBeDefined();
    expect(screen.getByText('Research Assistant')).toBeDefined();
  });

  it('renders StatusBadge for completed indexed state', () => {
    render(<StatusBadge status="completed" />);
    expect(screen.getByText('Indexed')).toBeDefined();
  });

  it('renders StatusBadge for in-flight extracting state', () => {
    render(<StatusBadge status="extracting" />);
    expect(screen.getByText('extracting...')).toBeDefined();
  });

  it('renders CitationChip with filename and page numbers', () => {
    const mockCitation = {
      citation_id: 'cite:1',
      document_id: 'doc_123',
      filename: 'attention_is_all_you_need.pdf',
      page_numbers: [6],
      chunk_ids: ['chunk_abc'],
      excerpt: 'Table 1 shows maximum path lengths...',
    };

    render(<CitationChip citation={mockCitation} />);
    expect(screen.getByText('[cite:1]')).toBeDefined();
    expect(screen.getByText('attention_is_all_you_need.pdf')).toBeDefined();
    expect(screen.getByText('p. 6')).toBeDefined();
  });
});
