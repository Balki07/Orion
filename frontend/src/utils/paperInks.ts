/**
 * Deterministic Per-Paper Ink Palette for "The Reading Room"
 * Palette:
 *  1. Deep Scholar Teal: #1F7A7A
 *  2. Amber Ochre:       #D99A2B
 *  3. Terracotta Brick:  #D2492A
 *  4. Scholar Indigo:    #4B5BA8
 *  5. Sage Olive:        #6E8B3D
 *  6. Mulberry Plum:     #8A4F7D
 */

export interface PaperInk {
  index: number;
  hex: string;
  name: string;
  bgLight: string;
  borderLight: string;
  bgDark: string;
  borderDark: string;
  textDark: string;
}

export const PAPER_INKS: PaperInk[] = [
  {
    index: 0,
    hex: '#1F7A7A',
    name: 'Scholar Teal',
    bgLight: 'rgba(31, 122, 122, 0.10)',
    borderLight: 'rgba(31, 122, 122, 0.35)',
    bgDark: 'rgba(31, 122, 122, 0.22)',
    borderDark: 'rgba(31, 122, 122, 0.55)',
    textDark: '#5EC4C4',
  },
  {
    index: 1,
    hex: '#D99A2B',
    name: 'Amber Ochre',
    bgLight: 'rgba(217, 154, 43, 0.12)',
    borderLight: 'rgba(217, 154, 43, 0.40)',
    bgDark: 'rgba(217, 154, 43, 0.22)',
    borderDark: 'rgba(217, 154, 43, 0.55)',
    textDark: '#F3C471',
  },
  {
    index: 2,
    hex: '#D2492A',
    name: 'Terracotta Brick',
    bgLight: 'rgba(210, 73, 42, 0.10)',
    borderLight: 'rgba(210, 73, 42, 0.35)',
    bgDark: 'rgba(210, 73, 42, 0.22)',
    borderDark: 'rgba(210, 73, 42, 0.55)',
    textDark: '#F18872',
  },
  {
    index: 3,
    hex: '#4B5BA8',
    name: 'Scholar Indigo',
    bgLight: 'rgba(75, 91, 168, 0.10)',
    borderLight: 'rgba(75, 91, 168, 0.35)',
    bgDark: 'rgba(75, 91, 168, 0.22)',
    borderDark: 'rgba(75, 91, 168, 0.55)',
    textDark: '#9AA7E5',
  },
  {
    index: 4,
    hex: '#6E8B3D',
    name: 'Sage Olive',
    bgLight: 'rgba(110, 139, 61, 0.12)',
    borderLight: 'rgba(110, 139, 61, 0.40)',
    bgDark: 'rgba(110, 139, 61, 0.22)',
    borderDark: 'rgba(110, 139, 61, 0.55)',
    textDark: '#A8C974',
  },
  {
    index: 5,
    hex: '#8A4F7D',
    name: 'Mulberry Plum',
    bgLight: 'rgba(138, 79, 125, 0.10)',
    borderLight: 'rgba(138, 79, 125, 0.35)',
    bgDark: 'rgba(138, 79, 125, 0.22)',
    borderDark: 'rgba(138, 79, 125, 0.55)',
    textDark: '#CE94C2',
  },
];

/**
 * Deterministically get ink for a given document ID or filename.
 */
export function getPaperInk(docKey: string, explicitIndex?: number): PaperInk {
  if (typeof explicitIndex === 'number' && explicitIndex >= 0) {
    return PAPER_INKS[explicitIndex % PAPER_INKS.length];
  }

  let hash = 0;
  for (let i = 0; i < docKey.length; i++) {
    hash = (hash * 31 + docKey.charCodeAt(i)) >>> 0;
  }
  return PAPER_INKS[hash % PAPER_INKS.length];
}

/**
 * Extract clean single-character paper initial from filename or title
 * e.g., "Rita Garcia.pdf" -> "R", "isi_31.07_22.pdf" -> "I", "1997_Paper.pdf" -> "P"
 */
export function getPaperInitial(filenameOrTitle: string): string {
  if (!filenameOrTitle) return 'P';
  // Strip path or extension if present
  const base = filenameOrTitle.split('/').pop()?.split('\\').pop() || filenameOrTitle;
  const clean = base.replace(/\.pdf$/i, '').trim();
  // Find first alphabet letter
  const match = clean.match(/[a-zA-Z]/);
  return (match ? match[0] : clean.charAt(0) || 'P').toUpperCase();
}
