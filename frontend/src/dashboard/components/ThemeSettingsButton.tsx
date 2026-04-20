import { useEffect, useRef, useState } from 'react';
import { ChevronDownIcon, MoonIcon, SettingsIcon, SunIcon } from './icons';

export type ThemeMode = 'dark' | 'light';

interface ThemeSettingsButtonProps {
  theme: ThemeMode;
  onThemeChange: (theme: ThemeMode) => void;
}

export const ThemeSettingsButton = ({ theme, onThemeChange }: ThemeSettingsButtonProps) => {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const handlePointerDown = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleEscape);
    };
  }, []);

  return (
    <div ref={menuRef} className="relative z-[120]">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="theme-top-button"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <span className="theme-accent-icon flex h-10 w-10 items-center justify-center rounded-2xl">
          <SettingsIcon />
        </span>
        <span className="hidden sm:flex sm:flex-col sm:items-start">
          <span className="text-sm font-medium theme-title">Appearance</span>
          <span className="text-xs theme-muted">
            {theme === 'dark' ? 'Dark mode enabled' : 'Light mode enabled'}
          </span>
        </span>
        <ChevronDownIcon
          className={[
            'theme-muted transition duration-200',
            open ? 'rotate-180' : ''
          ].join(' ')}
        />
      </button>

      {open ? (
        <div
          role="menu"
          className="theme-menu-panel absolute right-0 top-[calc(100%+0.75rem)] z-[140] min-w-[260px] p-3"
        >
          <div className="px-2 pb-3">
            <p className="panel-eyebrow">Appearance</p>
            <p className="mt-2 text-sm theme-copy">
              Choose the theme that feels more comfortable for everyday use.
            </p>
          </div>

          <div className="space-y-2">
            {[
              {
                id: 'dark' as const,
                label: 'Dark mode',
                description: 'A darker interface that is easier on the eyes.',
                Icon: MoonIcon
              },
              {
                id: 'light' as const,
                label: 'Light mode',
                description: 'A brighter interface for normal daytime use.',
                Icon: SunIcon
              }
            ].map(({ id, label, description, Icon }) => {
              const selected = theme === id;

              return (
                <button
                  key={id}
                  type="button"
                  role="menuitemradio"
                  aria-checked={selected}
                  onClick={() => {
                    onThemeChange(id);
                    setOpen(false);
                  }}
                  className={[
                    'flex w-full items-start gap-3 rounded-2xl border px-3 py-3 text-left transition',
                    selected
                      ? 'border-cyan-400/30 bg-cyan-400/12'
                      : 'theme-subtle-card hover:border-[color:var(--border-strong)]'
                  ].join(' ')}
                >
                  <span className="theme-accent-icon mt-0.5 flex h-10 w-10 items-center justify-center rounded-2xl">
                    <Icon />
                  </span>
                  <span className="flex-1">
                    <span className="block text-sm font-medium theme-title">{label}</span>
                    <span className="mt-1 block text-xs leading-5 theme-muted">{description}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
};
