import { ResearchPreferences } from '../types';

export const RESEARCH_PREFS_KEY = 'orion_research_preferences';

export const DEFAULT_RESEARCH_PREFERENCES: ResearchPreferences = {
  preferredAnswerStyle: 'comprehensive',
  citationDisplayPreference: 'inline_chips',
  defaultResearchScope: 'all_documents',
  defaultTopK: 8,
};

export function getResearchPreferences(): ResearchPreferences {
  if (typeof window === 'undefined') return DEFAULT_RESEARCH_PREFERENCES;
  try {
    const raw = localStorage.getItem(RESEARCH_PREFS_KEY);
    if (!raw) return DEFAULT_RESEARCH_PREFERENCES;
    const parsed = JSON.parse(raw);
    return {
      preferredAnswerStyle: parsed.preferredAnswerStyle || DEFAULT_RESEARCH_PREFERENCES.preferredAnswerStyle,
      citationDisplayPreference: parsed.citationDisplayPreference || DEFAULT_RESEARCH_PREFERENCES.citationDisplayPreference,
      defaultResearchScope: parsed.defaultResearchScope || DEFAULT_RESEARCH_PREFERENCES.defaultResearchScope,
      defaultTopK: typeof parsed.defaultTopK === 'number' ? parsed.defaultTopK : DEFAULT_RESEARCH_PREFERENCES.defaultTopK,
    };
  } catch {
    return DEFAULT_RESEARCH_PREFERENCES;
  }
}

export function saveResearchPreferences(prefs: ResearchPreferences): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(RESEARCH_PREFS_KEY, JSON.stringify(prefs));
  } catch {
    // Ignore in restricted environments
  }
}

