import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { ResearchWorkspace, getPlainFallbackBanner } from '../src/features/research/ResearchWorkspace';
import { api } from '../src/services/api';
import { ChatMessageItem } from '../src/types';

vi.mock('../src/services/api', () => ({
  api: {
    listDocuments: vi.fn(),
    getSettings: vi.fn(),
    askQuestion: vi.fn(),
    saveNote: vi.fn(),
  },
}));

describe('ResearchWorkspace Banner & Header Fallback Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.listDocuments as any).mockResolvedValue({
      items: [
        {
          id: 'doc1',
          filename: 'test_paper.pdf',
          page_count: 5,
          chunk_count: 12,
          status: 'completed',
        },
      ],
      total: 1,
    });
    (api.getSettings as any).mockResolvedValue({
      active_gemini_model: 'gemini-3.5-flash-lite',
      gemini_requests_per_minute: 15,
    });
  });

  describe('getPlainFallbackBanner helper', () => {
    it('returns plain message for QUOTA with zero raw exception names', () => {
      const msg: ChatMessageItem = {
        id: '1',
        role: 'assistant',
        content: 'Answer',
        timestamp: new Date().toISOString(),
        answer_path: 'deterministic_fallback',
        fallback_reason: 'QUOTA',
        warnings: ['ClientError: 429 RESOURCE_EXHAUSTED'],
      };
      const banner = getPlainFallbackBanner(msg);
      expect(banner).toBe('Gemini daily limit reached, using basic mode');
      expect(banner).not.toContain('ClientError');
      expect(banner).not.toContain('429');
    });

    it('returns plain message for BAD_KEY', () => {
      const msg: ChatMessageItem = {
        id: '2',
        role: 'assistant',
        content: 'Answer',
        timestamp: new Date().toISOString(),
        answer_path: 'deterministic_fallback',
        fallback_reason: 'BAD_KEY',
      };
      const banner = getPlainFallbackBanner(msg);
      expect(banner).toBe('Gemini key problem, using basic mode');
    });

    it('returns plain message for KEY_NOT_LOADED', () => {
      const msg: ChatMessageItem = {
        id: '3',
        role: 'assistant',
        content: 'Answer',
        timestamp: new Date().toISOString(),
        answer_path: 'deterministic_fallback',
        fallback_reason: 'KEY_NOT_LOADED',
      };
      const banner = getPlainFallbackBanner(msg);
      expect(banner).toBe('Gemini key not configured, using basic mode');
    });

    it('returns plain message for MODEL_NOT_FOUND', () => {
      const msg: ChatMessageItem = {
        id: '4',
        role: 'assistant',
        content: 'Answer',
        timestamp: new Date().toISOString(),
        answer_path: 'deterministic_fallback',
        fallback_reason: 'MODEL_NOT_FOUND',
      };
      const banner = getPlainFallbackBanner(msg);
      expect(banner).toBe('Gemini model unavailable, using basic mode');
    });

    it('strips raw exception names from legacy warnings', () => {
      const msg: ChatMessageItem = {
        id: '5',
        role: 'assistant',
        content: 'Answer',
        timestamp: new Date().toISOString(),
        warnings: ['Gemini API unavailable (ClientError). Using basic mode.'],
      };
      const banner = getPlainFallbackBanner(msg);
      expect(banner).not.toContain('ClientError');
    });
  });

  describe('Component rendering header and banner based on answer_path', () => {
    it('renders initial configured model when no messages exist', async () => {
      render(<ResearchWorkspace />);
      await waitFor(() => {
        expect(screen.getByTestId('header-model-label').textContent).toBe('gemini-3.5-flash-lite');
      });
      expect(screen.queryByTestId('fallback-banner')).toBeNull();
    });

    it('updates header to Deterministic mode and shows banner when fallback occurs', async () => {
      (api.askQuestion as any).mockResolvedValueOnce({
        answer: 'Deterministic synthesized answer without Gemini.',
        claims: [],
        citations: [],
        insufficient_evidence: false,
        answer_path: 'deterministic_fallback',
        model: null,
        fallback_reason: 'QUOTA',
        warnings: ['Gemini daily limit reached, using basic mode.'],
      });

      render(<ResearchWorkspace />);
      await waitFor(() => {
        expect(screen.getByTestId('header-model-label').textContent).toBe('gemini-3.5-flash-lite');
      });

      // Submit an example question
      const exampleBtn = screen.getByText('"What is the computational complexity of self-attention per layer?"');
      exampleBtn.click();

      await waitFor(() => {
        const verifyBtn = screen.getByRole('button', { name: /verify/i }) as HTMLButtonElement;
        expect(verifyBtn.disabled).toBe(false);
        verifyBtn.click();
      });

      // Header should switch to Deterministic mode
      await waitFor(() => {
        expect(screen.getByTestId('header-model-label').textContent).toBe('Deterministic mode');
      });

      // Banner should be rendered with plain language
      const banner = screen.getByTestId('fallback-banner');
      expect(banner.textContent).toContain('Gemini daily limit reached, using basic mode');
      expect(banner.textContent).not.toContain('ClientError');
      expect(banner.textContent).not.toContain('429');
    });

    it('maintains Gemini model in header and hides banner when answer_path is gemini', async () => {
      (api.askQuestion as any).mockResolvedValueOnce({
        answer: 'Gemini generated answer.',
        claims: [],
        citations: [],
        insufficient_evidence: false,
        answer_path: 'gemini',
        model: 'gemini-3.5-flash-lite',
        fallback_reason: null,
        warnings: [],
      });

      render(<ResearchWorkspace />);
      await waitFor(() => {
        expect(screen.getByTestId('header-model-label').textContent).toBe('gemini-3.5-flash-lite');
      });

      const exampleBtn = screen.getByText('"What is the computational complexity of self-attention per layer?"');
      exampleBtn.click();

      await waitFor(() => {
        const verifyBtn = screen.getByRole('button', { name: /verify/i }) as HTMLButtonElement;
        expect(verifyBtn.disabled).toBe(false);
        verifyBtn.click();
      });

      await waitFor(() => {
        expect(screen.getByTestId('header-model-label').textContent).toBe('gemini-3.5-flash-lite');
      });

      expect(screen.queryByTestId('fallback-banner')).toBeNull();
    });
  });
});
