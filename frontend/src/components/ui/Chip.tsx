import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { getPaperInk, getPaperInitial } from '../../utils/paperInks';

export interface ChipProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  docKey?: string;
  paperIndex?: number;
  filename?: string;
  citationId?: string;
  pageNumber?: number | string;
  isActive?: boolean;
}

export const Chip: React.FC<ChipProps> = ({
  className,
  docKey = '',
  paperIndex,
  filename = '',
  citationId,
  pageNumber,
  isActive = false,
  children,
  onClick,
  ...props
}) => {
  const ink = getPaperInk(docKey || filename, paperIndex);
  const initial = getPaperInitial(filename || docKey);

  return (
    <button
      type="button"
      onClick={onClick}
      className={twMerge(
        clsx(
          'inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono transition-all',
          'border select-none focus:outline-none focus:ring-2 focus:ring-reading-primary focus:ring-offset-1',
          isActive
            ? 'ring-2 ring-reading-primary shadow-subtle font-semibold'
            : 'hover:brightness-95 active:scale-95',
          className
        )
      )}
      style={{
        backgroundColor: ink.bgLight,
        borderColor: ink.borderLight,
        color: ink.hex,
      }}
      {...props}
    >
      {/* Paper initial badge so color is never the only signal */}
      <span
        className="w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold text-white shrink-0 shadow-xs"
        style={{ backgroundColor: ink.hex }}
        aria-hidden="true"
      >
        {initial}
      </span>

      {citationId && (
        <span className="font-semibold tracking-tight">[{citationId}]</span>
      )}

      {children}

      {pageNumber !== undefined && pageNumber !== null && (
        <span className="text-[10px] opacity-80">p. {pageNumber}</span>
      )}
    </button>
  );
};
