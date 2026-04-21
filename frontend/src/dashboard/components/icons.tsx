import { ComponentPropsWithoutRef } from 'react';

type IconProps = ComponentPropsWithoutRef<'svg'>;

const iconClass = 'h-5 w-5';

export const OverviewIcon = ({ className = '', ...props }: IconProps) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    className={`${iconClass} ${className}`}
    {...props}
  >
    <path d="M4 13h6V4H4v9Z" />
    <path d="M14 20h6v-6h-6v6Z" />
    <path d="M14 10h6V4h-6v6Z" />
    <path d="M4 20h6v-3H4v3Z" />
  </svg>
);

export const AgentsIcon = ({ className = '', ...props }: IconProps) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    className={`${iconClass} ${className}`}
    {...props}
  >
    <path d="M16 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2" />
    <circle cx="9.5" cy="7" r="4" />
    <path d="M20 8v6" />
    <path d="M23 11h-6" />
  </svg>
);

export const NetworkIcon = ({ className = '', ...props }: IconProps) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    className={`${iconClass} ${className}`}
    {...props}
  >
    <circle cx="6" cy="6" r="2.5" />
    <circle cx="18" cy="6" r="2.5" />
    <circle cx="12" cy="18" r="2.5" />
    <path d="M8.3 7.2 10.7 15" />
    <path d="M15.7 7.2 13.3 15" />
    <path d="M8.5 6h7" />
  </svg>
);

export const SettingsIcon = ({ className = '', ...props }: IconProps) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    className={`${iconClass} ${className}`}
    {...props}
  >
    <path d="m12 3 1.5 2.7 3.1.4-2.2 2.1.5 3.1L12 9.9 9.1 11.3l.5-3.1-2.2-2.1 3.1-.4L12 3Z" />
    <circle cx="12" cy="14" r="4" />
  </svg>
);

export const ControlIcon = ({ className = '', ...props }: IconProps) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    className={`${iconClass} ${className}`}
    {...props}
  >
    <path d="M12 3v7" />
    <path d="M7.2 5.2A8 8 0 1 0 16.8 5.2" />
    <path d="M9 13.5 11 15l4-4" />
  </svg>
);

export const PulseIcon = ({ className = '', ...props }: IconProps) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    className={`${iconClass} ${className}`}
    {...props}
  >
    <path d="M3 12h4l2-5 4 10 2-5h6" />
  </svg>
);

export const SignalIcon = ({ className = '', ...props }: IconProps) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    className={`${iconClass} ${className}`}
    {...props}
  >
    <path d="M5 19V9" />
    <path d="M10 19V5" />
    <path d="M15 19v-8" />
    <path d="M20 19v-4" />
  </svg>
);

export const TaskIcon = ({ className = '', ...props }: IconProps) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    className={`${iconClass} ${className}`}
    {...props}
  >
    <path d="M9 11 12 14l8-8" />
    <path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9" />
  </svg>
);

export const InfoIcon = ({ className = '', ...props }: IconProps) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    className={`${iconClass} ${className}`}
    {...props}
  >
    <circle cx="12" cy="12" r="9" />
    <path d="M12 10v5" />
    <path d="M12 7h.01" />
  </svg>
);

export const WarningIcon = ({ className = '', ...props }: IconProps) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    className={`${iconClass} ${className}`}
    {...props}
  >
    <path d="M12 3 2 21h20L12 3Z" />
    <path d="M12 9v4" />
    <path d="M12 17h.01" />
  </svg>
);

export const ErrorIcon = ({ className = '', ...props }: IconProps) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    className={`${iconClass} ${className}`}
    {...props}
  >
    <circle cx="12" cy="12" r="9" />
    <path d="m15 9-6 6" />
    <path d="m9 9 6 6" />
  </svg>
);

export const BotIcon = ({ className = '', ...props }: IconProps) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    className={`${iconClass} ${className}`}
    {...props}
  >
    <rect x="5" y="8" width="14" height="10" rx="3" />
    <path d="M12 4v4" />
    <path d="M8.5 12h.01" />
    <path d="M15.5 12h.01" />
    <path d="M9 18v2" />
    <path d="M15 18v2" />
  </svg>
);

export const SdkIcon = ({ className = '', ...props }: IconProps) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    className={`${iconClass} ${className}`}
    {...props}
  >
    <rect x="4" y="5" width="16" height="11" rx="2.5" />
    <path d="M9 19h6" />
    <path d="M12 16v3" />
    <path d="m9 11 2-2-2-2" />
    <path d="m15 11-2-2 2-2" />
  </svg>
);

export const SunIcon = ({ className = '', ...props }: IconProps) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    className={`${iconClass} ${className}`}
    {...props}
  >
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2.5" />
    <path d="M12 19.5V22" />
    <path d="m4.93 4.93 1.77 1.77" />
    <path d="m17.3 17.3 1.77 1.77" />
    <path d="M2 12h2.5" />
    <path d="M19.5 12H22" />
    <path d="m4.93 19.07 1.77-1.77" />
    <path d="m17.3 6.7 1.77-1.77" />
  </svg>
);

export const MoonIcon = ({ className = '', ...props }: IconProps) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    className={`${iconClass} ${className}`}
    {...props}
  >
    <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
  </svg>
);

export const LanguageIcon = ({ className = '', ...props }: IconProps) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    className={`${iconClass} ${className}`}
    {...props}
  >
    <path d="M4 6h10" />
    <path d="M9 4v2c0 4.2-1.8 8.1-5 10.8" />
    <path d="M6.5 11.5c1.1 1.5 2.5 2.9 4.2 4" />
    <path d="M14 8h6" />
    <path d="m17 6 3 10" />
    <path d="m20 16-6 0" />
    <path d="m15 16 2-6" />
  </svg>
);

export const ChevronDownIcon = ({ className = '', ...props }: IconProps) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    className={`${iconClass} ${className}`}
    {...props}
  >
    <path d="m6 9 6 6 6-6" />
  </svg>
);
