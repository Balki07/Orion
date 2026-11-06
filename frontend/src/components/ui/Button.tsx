import React, { forwardRef } from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'primary',
      size = 'md',
      isLoading = false,
      disabled,
      children,
      type = 'button',
      ...props
    },
    ref
  ) => {
    const baseStyles =
      'inline-flex items-center justify-center font-medium rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-reading-primary focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none select-none text-sm';

    const variantStyles = {
      primary:
        'bg-reading-primary text-reading-primary-fg hover:bg-reading-primary-hover shadow-paper border border-transparent',
      secondary:
        'bg-paper-surface hover:bg-paper-raised text-ink border border-border-hairline shadow-subtle',
      outline:
        'bg-transparent hover:bg-paper-surface text-ink border border-border-hairline',
      ghost:
        'bg-transparent hover:bg-paper-surface text-ink-secondary hover:text-ink',
      danger:
        'bg-reading-warning text-white hover:opacity-90 shadow-subtle border border-transparent',
    };

    const sizeStyles = {
      sm: 'h-8 px-2.5 text-xs gap-1.5',
      md: 'h-9 px-3.5 text-sm gap-2',
      lg: 'h-11 px-5 text-base gap-2.5',
    };

    return (
      <button
        ref={ref}
        type={type}
        disabled={disabled || isLoading}
        className={twMerge(
          clsx(
            baseStyles,
            variantStyles[variant],
            sizeStyles[size],
            className
          )
        )}
        {...props}
      >
        {isLoading && (
          <span className="inline-block w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin mr-1.5" />
        )}
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';
