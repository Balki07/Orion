import React from 'react';

interface LogoProps {
  className?: string;
  size?: number;
  showWordmark?: boolean;
}

export const OrionLogo: React.FC<LogoProps> = ({
  className = '',
  size = 28,
  showWordmark = true,
}) => {
  return (
    <div className={`flex items-center gap-2.5 select-none ${className}`}>
      {/* Orbital geometric SVG icon */}
      <svg
        width={size}
        height={size}
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="text-navy-700"
      >
        {/* Outer elliptical orbit */}
        <ellipse
          cx="16"
          cy="16"
          rx="13.5"
          ry="6"
          transform="rotate(-30 16 16)"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeDasharray="2 2"
          className="opacity-40"
        />
        {/* Second complementary orbit */}
        <ellipse
          cx="16"
          cy="16"
          rx="13.5"
          ry="6"
          transform="rotate(30 16 16)"
          stroke="currentColor"
          strokeWidth="1.5"
          className="opacity-60"
        />
        {/* Central nucleus */}
        <circle cx="16" cy="16" r="3.5" fill="currentColor" />
        {/* Evidence node on orbit */}
        <circle cx="26" cy="12" r="1.75" fill="#2c614b" />
        <circle cx="6" cy="20" r="1.5" fill="#d97706" />
      </svg>

      {showWordmark && (
        <div className="flex flex-col">
          <span className="font-serif tracking-widest text-lg font-bold text-ink-950 uppercase leading-none">
            ORION
          </span>
          <span className="text-[9px] tracking-wider font-mono text-ink-500 uppercase mt-0.5">
            Research Assistant
          </span>
        </div>
      )}
    </div>
  );
};
