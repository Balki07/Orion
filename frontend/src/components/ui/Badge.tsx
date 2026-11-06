import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'verified' | 'warning' | 'highlight' | 'outline' | 'muted';
  size?: 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  className,
  variant = 'default',
  size = 'md',
  children,
  ...props
}) => {
  const baseStyles =
    'inline-flex items-center font-medium rounded-full select-none font-sans';

  const sizeStyles = {
    sm: 'text-[11px] px-2 py-0.5 leading-tight',
    md: 'text-xs px-2.5 py-1 leading-normal',
  };

  const variantStyles = {
    default:
      'bg-paper-raised text-ink border border-border-hairline',
    verified:
      'bg-reading-verified-bg text-reading-verified border border-reading-verified/30',
    warning:
      'bg-reading-warning-bg text-reading-warning border border-reading-warning/30',
    highlight:
      'bg-reading-highlight-bg text-ink border border-reading-highlight/40',
    outline:
      'bg-transparent text-ink-secondary border border-border-hairline',
    muted:
      'bg-paper-surface text-ink-muted border border-border-subtle',
  };

  return (
    <span
      className={twMerge(
        clsx(baseStyles, sizeStyles[size], variantStyles[variant], className)
      )}
      {...props}
    >
      {children}
    </span>
  );
};
