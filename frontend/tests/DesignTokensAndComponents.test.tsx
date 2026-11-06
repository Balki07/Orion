import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { getPaperInk, getPaperInitial, PAPER_INKS } from '../src/utils/paperInks';
import { Button } from '../src/components/ui/Button';
import { Badge } from '../src/components/ui/Badge';
import { Card } from '../src/components/ui/Card';
import { Chip } from '../src/components/ui/Chip';
import { ThemeProvider, useTheme } from '../src/context/ThemeContext';

describe('Phase 0: Reading Room Tokens & Component Kit Tests', () => {
  describe('Deterministic Per-Paper Inks', () => {
    it('returns exact palette of 6 scholarly ink colors', () => {
      expect(PAPER_INKS.length).toBe(6);
      expect(PAPER_INKS.map((ink) => ink.hex)).toEqual([
        '#1F7A7A', // Scholar Teal
        '#D99A2B', // Amber Ochre
        '#D2492A', // Terracotta Brick
        '#4B5BA8', // Scholar Indigo
        '#6E8B3D', // Sage Olive
        '#8A4F7D', // Mulberry Plum
      ]);
    });

    it('assigns paper inks deterministically based on key', () => {
      const ink1 = getPaperInk('Rita Garcia.pdf');
      const ink2 = getPaperInk('Rita Garcia.pdf');
      expect(ink1.hex).toBe(ink2.hex);

      // Explicit index overrides hash
      const explicitInk = getPaperInk('AnyKey', 2);
      expect(explicitInk.hex).toBe('#D2492A');
    });

    it('extracts single uppercase initial from paper title', () => {
      expect(getPaperInitial('Rita Garcia.pdf')).toBe('R');
      expect(getPaperInitial('isi_31.07_22.pdf')).toBe('I');
      expect(getPaperInitial('Somantri.pdf')).toBe('S');
      expect(getPaperInitial('1997_Attention.pdf')).toBe('A');
    });
  });

  describe('Theme Management & Persistence', () => {
    const TestThemeComponent = () => {
      const { theme, resolvedTheme, toggleTheme } = useTheme();
      return (
        <div>
          <span data-testid="theme-val">{theme}</span>
          <span data-testid="resolved-val">{resolvedTheme}</span>
          <button data-testid="toggle-btn" onClick={toggleTheme}>Toggle</button>
        </div>
      );
    };

    beforeEach(() => {
      localStorage.clear();
      document.documentElement.classList.remove('dark');
    });

    it('toggles theme correctly and updates class on document element', () => {
      render(
        <ThemeProvider>
          <TestThemeComponent />
        </ThemeProvider>
      );

      const toggleBtn = screen.getByTestId('toggle-btn');
      // Default in test environment is system (which resolves to light without matchMedia)
      expect(screen.getByTestId('theme-val').textContent).toBe('system');

      // First toggle: system -> light
      fireEvent.click(toggleBtn);
      expect(screen.getByTestId('theme-val').textContent).toBe('light');
      expect(document.documentElement.classList.contains('dark')).toBe(false);

      // Second toggle: light -> dark
      fireEvent.click(toggleBtn);
      expect(screen.getByTestId('theme-val').textContent).toBe('dark');
      expect(document.documentElement.classList.contains('dark')).toBe(true);
      expect(localStorage.getItem('orion-reading-room-theme')).toBe('dark');
    });
  });

  describe('UI Component Kit (Button, Card, Badge, Chip)', () => {
    it('renders Button with variants and sizes', () => {
      render(
        <Button variant="primary" size="md">
          Scholar Button
        </Button>
      );
      const btn = screen.getByRole('button', { name: 'Scholar Button' });
      expect(btn).toBeDefined();
      expect(btn.className).toContain('bg-reading-primary');
    });

    it('renders Card with hairline border and paper surface', () => {
      render(
        <Card variant="surface" data-testid="test-card">
          Card Content
        </Card>
      );
      const card = screen.getByTestId('test-card');
      expect(card.className).toContain('bg-paper-surface');
      expect(card.className).toContain('border-border-hairline');
    });

    it('renders Badge with verified styling', () => {
      render(<Badge variant="verified">Verified Citation</Badge>);
      expect(screen.getByText('Verified Citation')).toBeDefined();
    });

    it('renders Chip with paper initial badge and citation id', () => {
      render(
        <Chip
          filename="Rita Garcia.pdf"
          citationId="cite:1"
          pageNumber={7}
        >
          Rita Garcia
        </Chip>
      );

      // Must show initial 'R'
      expect(screen.getByText('R')).toBeDefined();
      // Must show citation ID
      expect(screen.getByText('[cite:1]')).toBeDefined();
      // Must show page number
      expect(screen.getByText('p. 7')).toBeDefined();
    });
  });
});
