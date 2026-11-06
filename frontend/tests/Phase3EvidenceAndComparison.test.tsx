import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import '@testing-library/jest-dom';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { PdfEvidenceViewer } from '../src/features/research/PdfEvidenceViewer';
import { EvidenceInspector } from '../src/features/research/EvidenceInspector';
import { PaperComparisonView } from '../src/features/compare/PaperComparisonView';
import { api } from '../src/services/api';
import { CitationItem, DocumentItem, PaperComparisonResult } from '../src/types';

// Mock the API service
vi.mock('../src/services/api', () => ({
  api: {
    getDocument: vi.fn(),
    getDocumentPage: vi.fn(),
    getDocumentFileUrl: vi.fn((id: string) => `/api/v1/documents/${id}/file`),
    getDocumentPageRenderUrl: vi.fn((id: string, page: number, dpi: number = 150) => `/api/v1/documents/${id}/pages/${page}/render?dpi=${dpi}`),
    listDocuments: vi.fn(),
    comparePapers: vi.fn(),
  },
}));

describe('Phase 3: Evidence Inspector, PDF Viewer & Comparison Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockCitation1: CitationItem = {
    citation_id: 1,
    document_id: 'doc_vaswani_2017',
    filename: 'Attention Is All You Need.pdf',
    page_numbers: [2],
    excerpt: 'The Transformer uses multi-head self-attention mechanisms to dispense with recurrence entirely.',
    chunk_ids: ['chk_page_2_chunk_1'],
    confidence_score: 0.98,
  };

  const mockCitation2: CitationItem = {
    citation_id: 2,
    document_id: 'doc_devlin_2018',
    filename: 'BERT Pre-training of Deep Bidirectional Transformers.pdf',
    page_numbers: [4],
    excerpt: 'BERT is designed to pre-train deep bidirectional representations from unlabeled text.',
    chunk_ids: ['chk_page_4_chunk_1'],
    confidence_score: 0.95,
  };

  const mockCitation3: CitationItem = {
    citation_id: 3,
    document_id: 'doc_vaswani_2017',
    filename: 'Attention Is All You Need.pdf',
    page_numbers: [6],
    excerpt: 'On the WMT 2014 English-to-German translation task, the big transformer achieves a BLEU score of 28.4.',
    chunk_ids: ['chk_page_6_chunk_1'],
    confidence_score: 0.99,
  };

  const mockDocument: DocumentItem = {
    id: 'doc_vaswani_2017',
    filename: 'Attention Is All You Need.pdf',
    file_size: 2211840,
    page_count: 15,
    chunk_count: 24,
    status: 'completed',
    created_at: '2026-10-20T10:00:00Z',
    updated_at: '2026-10-20T10:05:00Z',
  };

  describe('1. PDF Evidence Viewer & Provenance', () => {
    it('opens the correct PDF and navigates to the cited page', async () => {
      vi.mocked(api.getDocument).mockResolvedValue(mockDocument);

      render(
        <PdfEvidenceViewer
          documentId={mockCitation1.document_id}
          filename={mockCitation1.filename}
          pageNumber={mockCitation1.page_numbers[0]}
          excerpt={mockCitation1.excerpt}
          citationId={mockCitation1.citation_id}
          chunkIds={mockCitation1.chunk_ids}
        />
      );

      // Verify filename and initial are rendered
      expect(screen.getByText('Attention Is All You Need.pdf')).toBeInTheDocument();
      // Verify page number indicator
      expect(screen.getAllByText(/Page 2/).length).toBeGreaterThan(0);
      // Verify image render URL matches cited page
      const img = screen.getByAltText('Page 2 of Attention Is All You Need.pdf');
      expect(img).toHaveAttribute('src', '/api/v1/documents/doc_vaswani_2017/pages/2/render?dpi=150');
      // Verify supporting excerpt is displayed without fabricating coordinates
      expect(screen.getByText(/The Transformer uses multi-head self-attention mechanisms/)).toBeInTheDocument();
      expect(screen.getByText(/Exact text coordinate bounding-box is not stored by document pipeline/)).toBeInTheDocument();
    });

    it('renders empty state when documentId is missing', () => {
      render(<PdfEvidenceViewer />);
      expect(screen.getByText('No Citation Selected')).toBeInTheDocument();
      expect(screen.getByText(/Click any numbered citation chip in an answer/)).toBeInTheDocument();
    });

    it('handles out-of-bounds invalid page numbers with warning banner and reset action', async () => {
      vi.mocked(api.getDocument).mockResolvedValue({
        ...mockDocument,
        page_count: 5,
      });

      render(
        <PdfEvidenceViewer
          documentId={mockCitation1.document_id}
          filename={mockCitation1.filename}
          pageNumber={99}
          excerpt={mockCitation1.excerpt}
          citationId={mockCitation1.citation_id}
        />
      );

      // Wait for document to load totalPages = 5
      await waitFor(() => {
        expect(screen.getByText('Invalid Page Number')).toBeInTheDocument();
      });
      expect(screen.getByText(/Page 99 is outside the document boundaries/)).toBeInTheDocument();

      // Click Jump to Page 1
      const jumpBtn = screen.getByRole('button', { name: /Jump to Page 1/i });
      fireEvent.click(jumpBtn);

      expect(screen.getByText(/Page 1 of 5/)).toBeInTheDocument();
    });

    it('provides multi-citation navigation with previous/next controls and keyboard shortcuts', async () => {
      vi.mocked(api.getDocument).mockResolvedValue(mockDocument);
      const onNavigateCitation = vi.fn();

      const allCitations = [mockCitation1, mockCitation2, mockCitation3];

      render(
        <PdfEvidenceViewer
          documentId={mockCitation1.document_id}
          filename={mockCitation1.filename}
          pageNumber={mockCitation1.page_numbers[0]}
          excerpt={mockCitation1.excerpt}
          citationId={mockCitation1.citation_id}
          allCitations={allCitations}
          currentCitationIndex={0}
          onNavigateCitation={onNavigateCitation}
        />
      );

      // Verify citation navigation bar is rendered
      expect(screen.getByTestId('citation-navigation-bar')).toBeInTheDocument();
      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();

      // Click Next
      const nextBtn = screen.getByRole('button', { name: /Next citation/i });
      fireEvent.click(nextBtn);
      expect(onNavigateCitation).toHaveBeenCalledWith('next');

      // Test keyboard shortcut ']'
      fireEvent.keyDown(window, { key: ']' });
      expect(onNavigateCitation).toHaveBeenCalledWith('next');

      // Test keyboard shortcut '['
      fireEvent.keyDown(window, { key: '[' });
      expect(onNavigateCitation).toHaveBeenCalledWith('prev');
    });

    it('allows switching to Extracted Text view and displays real page text', async () => {
      vi.mocked(api.getDocument).mockResolvedValue(mockDocument);
      vi.mocked(api.getDocumentPage).mockResolvedValue({
        document_id: 'doc_vaswani_2017',
        page_number: 2,
        text: 'Full extracted text of Page 2 from Attention paper.',
        character_count: 52,
        word_count: 9,
        has_text: true,
      });

      render(
        <PdfEvidenceViewer
          documentId={mockCitation1.document_id}
          filename={mockCitation1.filename}
          pageNumber={mockCitation1.page_numbers[0]}
          excerpt={mockCitation1.excerpt}
          citationId={mockCitation1.citation_id}
          chunkIds={mockCitation1.chunk_ids}
        />
      );

      // Switch to Extracted Text
      const textTab = screen.getByRole('button', { name: /Extracted Text/i });
      fireEvent.click(textTab);

      await waitFor(() => {
        expect(screen.getByText('Full extracted text of Page 2 from Attention paper.')).toBeInTheDocument();
      });
      expect(screen.getByText(/52 chars/)).toBeInTheDocument();
      expect(screen.getByText(/Indexed Chunk IDs: chk_page_2_chunk_1/)).toBeInTheDocument();
    });
  });

  describe('2. Evidence Inspector Integration', () => {
    it('renders lazy-loaded PDF viewer when activeCitation is provided', async () => {
      vi.mocked(api.getDocument).mockResolvedValue(mockDocument);

      render(
        <EvidenceInspector
          activeCitation={mockCitation1}
          allCitations={[mockCitation1, mockCitation2]}
          onClearCitation={vi.fn()}
          onOpenDocument={vi.fn()}
        />
      );

      // Top header Verified badge
      expect(screen.getByText('Verified')).toBeInTheDocument();
      // Lazy loaded viewer appears
      await waitFor(() => {
        expect(screen.getByTestId('pdf-evidence-viewer')).toBeInTheDocument();
      });
    });

    it('switches between PDF View and Metadata tabs', async () => {
      vi.mocked(api.getDocument).mockResolvedValue(mockDocument);

      render(
        <EvidenceInspector
          activeCitation={mockCitation1}
          allCitations={[mockCitation1]}
          onClearCitation={vi.fn()}
          onOpenDocument={vi.fn()}
        />
      );

      // Switch to Metadata tab
      const metaTab = screen.getByRole('button', { name: /Metadata/i });
      fireEvent.click(metaTab);

      expect(screen.getByText('Citation Provenance Target')).toBeInTheDocument();
      expect(screen.getByText(/chk_page_2_chunk_1/)).toBeInTheDocument();
    });
  });

  describe('3. Paper Comparison View & Empty States', () => {
    const mockDocA: DocumentItem = {
      id: 'doc_a',
      filename: 'Extended Producer Responsibility in EU.pdf',
      file_size: 1048576,
      page_count: 12,
      chunk_count: 18,
      status: 'completed',
      created_at: '2026-10-20T10:00:00Z',
      updated_at: '2026-10-20T10:05:00Z',
    };

    const mockDocB: DocumentItem = {
      id: 'doc_b',
      filename: 'Circular Economy Policy Assessment.pdf',
      file_size: 2097152,
      page_count: 18,
      chunk_count: 30,
      status: 'completed',
      created_at: '2026-10-20T10:00:00Z',
      updated_at: '2026-10-20T10:05:00Z',
    };

    it('renders initial invitation state and disables compare button when < 2 papers selected', async () => {
      vi.mocked(api.listDocuments).mockResolvedValue({
        total: 1,
        items: [mockDocA],
      });

      render(<PaperComparisonView />);

      await waitFor(() => {
        expect(screen.getByText('Multi-Paper Comparative Synthesis')).toBeInTheDocument();
      });

      // Invitation empty state
      expect(screen.getByText(/Ready for Multi-Paper Comparative Analysis/)).toBeInTheDocument();

      // Only 1 doc in list, so button is disabled
      const compareBtn = screen.getByRole('button', { name: /Compare Selected/i });
      expect(compareBtn).toBeDisabled();
    });

    it('displays honest empty state when 0 documents exist in scope', async () => {
      vi.mocked(api.listDocuments).mockResolvedValue({
        total: 0,
        items: [],
      });

      render(<PaperComparisonView />);

      await waitFor(() => {
        expect(screen.getByText('No Completed Publications in Scope')).toBeInTheDocument();
      });
      expect(screen.getByText(/Please upload or index research papers into the active scope/)).toBeInTheDocument();
    });

    it('renders side-by-side matrix, synthesis, contradictions, and research gaps from API', async () => {
      vi.mocked(api.listDocuments).mockResolvedValue({
        total: 2,
        items: [mockDocA, mockDocB],
      });

      const mockComparisonResult: PaperComparisonResult = {
        documents: [
          {
            document_id: 'doc_a',
            filename: 'Extended Producer Responsibility in EU.pdf',
            fields: {
              problem: {
                field_name: 'problem',
                extracted_text: 'Packaging waste volume increased 20% over 5 years.',
                citations: [mockCitation1],
                is_missing: false,
              },
              methodology: {
                field_name: 'methodology',
                extracted_text: 'Econometric panel regression across 27 EU member states.',
                citations: [],
                is_missing: false,
              },
              datasets: { field_name: 'datasets', extracted_text: 'Eurostat 2015-2022', citations: [], is_missing: false },
              results: { field_name: 'results', extracted_text: 'Fee modulation increased recycling by 14%.', citations: [], is_missing: false },
              limitations: { field_name: 'limitations', extracted_text: 'Data gaps in informal collection sectors.', citations: [], is_missing: false },
              future_work: { field_name: 'future_work', extracted_text: '', citations: [], is_missing: true },
            },
          },
          {
            document_id: 'doc_b',
            filename: 'Circular Economy Policy Assessment.pdf',
            fields: {
              problem: {
                field_name: 'problem',
                extracted_text: 'Municipal budget deficits from e-waste management.',
                citations: [],
                is_missing: false,
              },
              methodology: {
                field_name: 'methodology',
                extracted_text: 'Life cycle analysis and material flow accounting.',
                citations: [],
                is_missing: false,
              },
              datasets: { field_name: 'datasets', extracted_text: 'OECD circular metrics', citations: [], is_missing: false },
              results: { field_name: 'results', extracted_text: 'Disposal costs decreased by 8% under mandatory takeback.', citations: [], is_missing: false },
              limitations: { field_name: 'limitations', extracted_text: '', citations: [], is_missing: true },
              future_work: { field_name: 'future_work', extracted_text: 'Harmonizing cross-border definition standards.', citations: [], is_missing: false },
            },
          },
        ],
        synthesis: 'Both studies confirm that financial producer responsibility shifts collection burdens from municipalities.',
        contradictions: [
          'Study A identifies fee modulation as primary efficiency driver, whereas Study B reports mandatory takeback quotas generate superior yield.',
        ],
        research_gaps: [
          'Neither study quantifies informal plastic recycling leakage rates outside formal EPR registries.',
        ],
        latency_ms: { comparison_synthesis: 420.5 },
      };

      vi.mocked(api.comparePapers).mockResolvedValue(mockComparisonResult);

      render(<PaperComparisonView />);

      await waitFor(() => {
        expect(screen.getByText('Extended Producer Responsibility in EU.pdf')).toBeInTheDocument();
      });

      // Click Compare Selected (both are selected by default)
      const compareBtn = screen.getByRole('button', { name: /Compare Selected/i });
      fireEvent.click(compareBtn);

      // Verify Synthesis is rendered
      await waitFor(() => {
        expect(screen.getByText(/Both studies confirm that financial producer responsibility shifts collection burdens/)).toBeInTheDocument();
      });

      // Verify Contradictions section is rendered
      expect(screen.getByText(/Identified Contradictions & Divergent Findings/)).toBeInTheDocument();
      expect(screen.getByText(/Study A identifies fee modulation as primary efficiency driver/)).toBeInTheDocument();

      // Verify Research Gaps section is rendered
      expect(screen.getByText(/Identified Open Research Gaps/)).toBeInTheDocument();
      expect(screen.getByText(/Neither study quantifies informal plastic recycling leakage rates/)).toBeInTheDocument();

      // Verify Side-by-Side Matrix table is rendered with dimension data
      expect(screen.getByText('Packaging waste volume increased 20% over 5 years.')).toBeInTheDocument();
      expect(screen.getByText('Municipal budget deficits from e-waste management.')).toBeInTheDocument();

      // Verify honest missing dimension text
      expect(screen.getAllByText('No conclusive evidence found in this publication for this dimension.').length).toBeGreaterThan(0);
    });
  });
});
