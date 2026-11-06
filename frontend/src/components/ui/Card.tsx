import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'surface' | 'raised';
}

export const Card: React.FC<CardProps> = ({
  className,
  variant = 'default',
  children,
  ...props
}) => {
  const variantStyles = {
    default: 'bg-paper-card border border-border-hairline shadow-paper',
    surface: 'bg-paper-surface border border-border-hairline shadow-subtle',
    raised: 'bg-paper-raised border border-border-subtle shadow-paper-elevated',
  };

  return (
    <div
      className={twMerge(
        clsx(
          'rounded-md p-4 transition-colors',
          variantStyles[variant],
          className
        )
      )}
      {...props}
    >
      {children}
    </div>
  );
};
