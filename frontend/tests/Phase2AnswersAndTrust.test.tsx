import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { AnswerRenderer } from '../src/features/research/AnswerRenderer';
import { GroundingStrip } from '../src/features/research/GroundingStrip';
import { AbstentionBanner } from '../src/features/research/AbstentionBanner';
import { AnswerActions } from '../src/features/research/AnswerActions';
import { CitationItem, ClaimItem } from '../src/types';

const mockCitations: CitationItem[] = [
  {
    citation_id: 'cite:1',
    document_id: 'doc_somantri',
    filename: 'Somantri.pdf',
    page_numbers: [14],
    chunk_ids: ['chunk_somantri_14'],
    excerpt: 'The EPR regulatory framework mandates a 70% minimum collection target for post-consumer plastics.',
  },
  {
    citation_id: 'cite:2',
    document_id: 'doc_plastic_rules',
    filename: 'Plastic_Waste_Rules_2024.pdf',
    page_numbers: [8, 9],
    chunk_ids: ['chunk_pwr_8'],
    excerpt: 'Producers, importers, and brand owners must register on the centralized EPR portal.',
  },
];

const mockClaims: ClaimItem[] = [
  {
    text: 'EPR requires 70% post-consumer plastic collection.',
    citation_ids: ['cite:1'],
    support_status: 'supported',
  },
  {
    text: 'Brand owners must register on the national portal.',
    citation_ids: ['cite:2'],
    support_status: 'supported',
  },
  {
    text: 'Informal waste workers are fully subsidized under state funds.',
    citation_ids: [],
    support_status: 'unsupported',
  },
];

describe('Phase 2 Answers & Trust Tests', () => {
  describe('AnswerRenderer with Inline Citation Chips', () => {
    it('maps raw [cite:1] tokens into interactive inline CitationChips', () => {
      const handleCitationClick = vi.fn();
      const content = 'According to the plastic waste analysis [cite:1], collection quotas are mandatory.';

      render(
        <AnswerRenderer
          content={content}
          citations={mockCitations}
          onCitationClick={handleCitationClick}
        />
      );

      // Raw token [cite:1] should not be plain text; it should render as a citation button
      const chipBtn = screen.getByRole('button', { name: /Citation \[1\]/i });
      expect(chipBtn).toBeDefined();

      // Clicking the inline chip activates the citation
      fireEvent.click(chipBtn);
      expect(handleCitationClick).toHaveBeenCalledWith(mockCitations[0]);
    });

    it('renders scholarly markdown typography including headings, lists, and blockquotes', () => {
      const content = `
### Supported Findings by Source
- First finding with reference [cite:1]
- Second finding from regulation [cite:2]

> "Strict compliance is monitored by CPCB."
      `;

      render(<AnswerRenderer content={content} citations={mockCitations} />);

      expect(screen.getByText('Supported Findings by Source')).toBeDefined();
      expect(screen.getByText(/Strict compliance is monitored by CPCB/i)).toBeDefined();
    });
  });

  describe('GroundingStrip Claim Verification', () => {
    it('renders claim verification breakdown strictly from API data', () => {
      render(<GroundingStrip claims={mockClaims} citations={mockCitations} />);

      expect(screen.getByTestId('grounding-strip')).toBeDefined();
      expect(screen.getByText(/3 claims verified/i)).toBeDefined();
      expect(screen.getByText(/2 Supported/i)).toBeDefined();
      expect(screen.getByText(/1 Unsupported/i)).toBeDefined();
    });

    it('returns null when claims array is empty or undefined (never inventing data)', () => {
      const { container } = render(<GroundingStrip claims={[]} citations={mockCitations} />);
      expect(container.firstChild).toBeNull();
    });

    it('toggles claim expansion and allows clicking citation link', () => {
      const handleCitationClick = vi.fn();

      render(
        <GroundingStrip
          claims={mockClaims}
          citations={mockCitations}
          onCitationClick={handleCitationClick}
        />
      );

      // Expand accordion
      const toggleBtn = screen.getByRole('button', { name: /toggle claims breakdown list/i });
      fireEvent.click(toggleBtn);

      // Check expanded claim text
      expect(screen.getByText(/Informal waste workers are fully subsidized/i)).toBeDefined();

      // Click citation link on first claim
      const citeLink = screen.getAllByRole('button', { name: '[1]' })[0];
      fireEvent.click(citeLink);
      expect(handleCitationClick).toHaveBeenCalledWith(mockCitations[0]);
    });
  });

  describe('AbstentionBanner State', () => {
    it('renders calm scholarly abstention state when insufficient_evidence is true', () => {
      const handleOpenSources = vi.fn();

      render(
        <AbstentionBanner
          insufficientEvidence={true}
          reasonCode="RETRIEVAL_NO_CANDIDATES"
          traceId="trace_test_987"
          onOpenSources={handleOpenSources}
        />
      );

      expect(screen.getByTestId('abstention-banner')).toBeDefined();
      expect(screen.getByText(/Concept Not Found in Selected Literature/i)).toBeDefined();
      expect(screen.getByText(/Try expanding your scope to all indexed papers/i)).toBeDefined();
      expect(screen.getByText(/trace_test_987/i)).toBeDefined();

      const scopeBtn = screen.getByRole('button', { name: /Adjust Scope Sources/i });
      fireEvent.click(scopeBtn);
      expect(handleOpenSources).toHaveBeenCalledTimes(1);
    });

    it('returns null when insufficientEvidence is false', () => {
      const { container } = render(
        <AbstentionBanner insufficientEvidence={false} reasonCode="OK" />
      );
      expect(container.firstChild).toBeNull();
    });
  });

  describe('AnswerActions Real Operations', () => {
    beforeEach(() => {
      Object.assign(navigator, {
        clipboard: {
          writeText: vi.fn().mockResolvedValue(undefined),
        },
      });
    });

    it('formats and copies answer with bibliographic references to clipboard', async () => {
      render(
        <AnswerActions
          content="EPR collection targets are verified."
          citations={mockCitations}
          model="gemini-3.5-flash-lite"
          answerPath="gemini"
        />
      );

      const copyBtn = screen.getByRole('button', { name: /Copy answer with references/i });
      fireEvent.click(copyBtn);

      await waitFor(() => {
        expect(navigator.clipboard.writeText).toHaveBeenCalled();
        const copiedCall = (navigator.clipboard.writeText as any).mock.calls[0][0];
        expect(copiedCall).toContain('EPR collection targets are verified.');
        expect(copiedCall).toContain('### References');
        expect(copiedCall).toContain('[1] Somantri.pdf (p. 14)');
      });
    });

    it('invokes onSaveToNotes and onRegenerate handlers', () => {
      const handleSave = vi.fn().mockResolvedValue(undefined);
      const handleRegen = vi.fn();

      render(
        <AnswerActions
          content="EPR analysis"
          citations={mockCitations}
          model="gemini-3.5-flash-lite"
          answerPath="gemini"
          onSaveToNotes={handleSave}
          onRegenerate={handleRegen}
        />
      );

      const saveBtn = screen.getByRole('button', { name: /Save answer to research notes/i });
      fireEvent.click(saveBtn);
      expect(handleSave).toHaveBeenCalledTimes(1);

      const regenBtn = screen.getByRole('button', { name: /Regenerate synthesis/i });
      fireEvent.click(regenBtn);
      expect(handleRegen).toHaveBeenCalledTimes(1);
    });

    it('displays distinct attribution for Gemini vs Deterministic mode', () => {
      const { rerender } = render(
        <AnswerActions
          content="Gemini answer"
          model="gemini-3.5-flash-lite"
          answerPath="gemini"
        />
      );
      expect(screen.getByText('gemini-3.5-flash-lite')).toBeDefined();

      rerender(
        <AnswerActions
          content="Fallback answer"
          model={null}
          answerPath="deterministic_fallback"
          fallbackReason="QUOTA"
        />
      );
      expect(screen.getByText('Deterministic mode')).toBeDefined();
    });
  });
});
