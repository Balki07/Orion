import React from 'react';
import { Sun, Moon, Laptop } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import { Tooltip } from './Tooltip';

export const ThemeToggle: React.FC<{ className?: string }> = ({ className = '' }) => {
  const { theme, toggleTheme, resolvedTheme } = useTheme();

  const labels = {
    light: 'Light: Paper',
    dark: 'Dark: Midnight Library',
    system: 'System Preference',
  };

  return (
    <Tooltip content={`Theme: ${labels[theme]} (Click to toggle)`}>
      <button
        type="button"
        onClick={toggleTheme}
        aria-label={`Current theme is ${theme}. Click to switch theme.`}
        className={`p-2 rounded-md border border-border-hairline bg-paper-surface hover:bg-paper-raised text-ink transition-colors focus:outline-none focus:ring-2 focus:ring-reading-primary ${className}`}
      >
        {theme === 'system' ? (
          <Laptop className="w-4 h-4 text-ink-secondary" />
        ) : resolvedTheme === 'dark' ? (
          <Moon className="w-4 h-4 text-reading-primary" />
        ) : (
          <Sun className="w-4 h-4 text-reading-highlight" />
        )}
      </button>
    </Tooltip>
  );
};
